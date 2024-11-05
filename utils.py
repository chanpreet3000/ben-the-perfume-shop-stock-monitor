import random
from urllib.parse import parse_qs, urlparse

import discord
import pytz
import aiohttp
import json
from datetime import datetime
from typing import Tuple
from Logger import Logger
from bs4 import BeautifulSoup
from models import ProductData, ProductOptions
from ProxyManager import ProxyManager

WINDOWS_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Vivaldi/6.5.3206.63'
]

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.7',
    'cache-control': 'max-age=0',
    'if-none-match': 'W/"126857-d1r5C6RINRe9aCoeR5q37Isq5lU:dtagent10299241001084140w6IF:dtagent10299241001084140w6IF:dtagent10299241001084140w6IF"',
    'priority': 'u=0, i',
    'sec-ch-ua': '"Chromium";v="130", "Brave";v="130", "Not?A_Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'sec-gpc': '1',
    'upgrade-insecure-requests': '1',
    'user-agent': random.choice(WINDOWS_USER_AGENTS),
}


def get_current_time():
    uk_tz = pytz.timezone('Europe/London')
    return datetime.now(uk_tz).strftime('%d %B %Y, %I:%M:%S %p %Z')


def get_product_embed(product_data: ProductData) -> discord.Embed:
    embed = discord.Embed(title=product_data.name, url=product_data.product_url, color=0x00ff00)

    embed.add_field(
        name='Product EAN',
        value=product_data.ean,
        inline=False
    )

    for option in product_data.options:
        embed.add_field(
            name='Variant',
            value=option.name,
            inline=True
        )
        embed.add_field(
            name='Price',
            value=option.formatted_price,
            inline=True
        )
        embed.add_field(
            name='Stock',
            value=f"{option.stock_level} - {option.stock_status}",
            inline=True
        )
        embed.add_field(
            name='\u200b',
            value='\u200b',
            inline=False
        )

    embed.set_footer(text=f"🕒 Time: {get_current_time()} (UK)")
    return embed


async def fetch_product_data(url: str, max_retries=5) -> Tuple[discord.Embed, ProductData | None]:
    if not (url.startswith('https://www.theperfumeshop.com/') and '?varSel=' in url):
        raise ValueError(
            "Invalid URL. Must be a valid The Perfume Shop product URL containing '?varSel='. Eg: https://www.theperfumeshop.com/marc-jacobs/perfect/eau-de-parfum-gift-set/p/267910EDPXS?varSel=1298801")

    proxy_manager = ProxyManager()
    await proxy_manager.initialize()

    for attempt in range(max_retries):
        try:
            random_proxy = await proxy_manager.get_proxy()
            Logger.info(f'Attempt {attempt + 1}: Fetching product data from {url} using proxy {random_proxy}')

            conn = aiohttp.TCPConnector(ssl=True)
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.get(
                        url,
                        headers=headers,
                        cookies={},
                        proxy=random_proxy['http'],
                        timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        raise Exception(f'HTTP error {response.status}')

                    content = await response.text()

            # Parse the page content
            soup = BeautifulSoup(content, 'html.parser')

            # Locate the script tag with the product data
            script_tag = soup.find(id='spartacus-app-state')
            if not script_tag:
                raise Exception('Product data not found in the page')

            # Process the script content as JSON
            try:
                cleaned_content = script_tag.string.replace('&q;', '"').replace('&l;', '<').replace('&g;', '>')
                data = json.loads(cleaned_content)['cx-state']['product']['details']['entities']
            except json.JSONDecodeError:
                raise Exception('Failed to parse product JSON data')

            # Find the specific item containing product code
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            product_code = query_params.get('varSel')[0] if query_params.get('varSel') else None

            if product_code:
                Logger.info(f"Found product code: {product_code}")
            else:
                raise Exception("Product code not found")

            details = data[product_code]['details']['value']
            product_name = details['name']
            ean = details['ean']

            options = details['baseOptions'][0]['options']
            selected = details['baseOptions'][0]['selected']

            default_stock_level = selected['stock']['stockLevel']
            default_stock_status = selected['stock']['stockLevelStatus']

            default_formatted_price = selected['priceData']['formattedValue']

            # Process each option to extract variant information
            options_data = []
            for option in options:
                try:
                    variant_name = f"{product_name} - {option['variantOptionQualifiers'][0]['value']}"
                except (KeyError, IndexError):
                    variant_name = product_name

                try:
                    stock_level = option['stock']['stockLevel']
                    stock_status = option['stock']['stockLevelStatus']
                except KeyError:
                    stock_level = default_stock_level
                    stock_status = default_stock_status

                try:
                    formatted_price = option['priceData']['formattedValue']
                except KeyError:
                    formatted_price = default_formatted_price

                options_data.append(
                    ProductOptions(
                        name=variant_name,
                        stock_level=stock_level,
                        is_in_stock=stock_status != 'outOfStock',
                        stock_status=stock_status,
                        product_code=option['code'],
                        formatted_price=formatted_price
                    )
                )

            product_data = ProductData(
                ean=ean,
                name=product_name,
                product_code=product_code,
                options=options_data,
                product_url=url
            )
            Logger.info(f'Successfully fetched product data from {url}', product_data.to_dict())
            return get_product_embed(product_data), product_data
        except Exception as e:
            Logger.error(f'Error fetching product data from {url}', e)
            continue

    Logger.error(f'Error fetching product data from {url}')
    return discord.Embed(
        title='Error',
        description=f'Failed to fetch product data from {url}.  Please make sure the url is correct',
        color=0xff0000
    ), None
