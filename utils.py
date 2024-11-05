import os
import random

import discord
import pytz
import requests
import json
from fake_useragent import UserAgent
from datetime import datetime
from typing import Tuple
from Logger import Logger
from bs4 import BeautifulSoup
from typing import List, Dict
from dotenv import load_dotenv

from models import ProductData, ProductOptions

load_dotenv()


def get_random_headers():
    ua = UserAgent()

    return {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.5',
        'cache-control': 'max-age=0',
        'if-none-match': 'W/"13575d-3DwWx3/tr8nJdLbqIxt1UGPnEpE"',
        'priority': 'u=0, i',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'sec-gpc': '1',
        'upgrade-insecure-requests': '1',
        'user-agent': ua.random,
    }


def get_proxies_from_webshare() -> List[Dict[str, str]]:
    countries: List[str] = ['US', 'GB']
    WEBSHARE_API_TOKEN = os.getenv('WEBSHARE_API_TOKEN')
    formatted_proxies = []
    page = 1

    while True:
        response = requests.get(
            f"https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page={page}&page_size=100",
            headers={"Authorization": f"Token {WEBSHARE_API_TOKEN}"}
        )

        if response.status_code != 200:
            raise Exception(f"API request failed with status code: {response.status_code}")

        proxies_data = response.json()
        proxies_list = proxies_data.get('results', [])

        if not proxies_list:
            break

        # Filter proxies by country
        for proxy in proxies_list:
            if proxy.get('country_code') in countries:
                proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['proxy_address']}:{proxy['port']}"
                formatted_proxies.append({'http': proxy_url, 'https': proxy_url})

        # Check if we've reached the last page
        if not proxies_data.get('next'):
            break

        page += 1

    if len(formatted_proxies) == 0:
        raise Exception(f"No proxies available for countries: {', '.join(countries)}")

    Logger.info(f"Loaded {len(formatted_proxies)} proxies from Webshare for countries: {', '.join(countries)}")
    return formatted_proxies


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


def fetch_product_data(url: str, max_retries=5) -> Tuple[discord.Embed, ProductData | None]:
    if not url.startswith('https://www.theperfumeshop.com/'):
        raise ValueError('Invalid URL. Must be a valid The Perfume Shop product URL')
    proxies = get_proxies_from_webshare()
    for attempt in range(max_retries):
        try:
            random_proxy = random.choice(proxies)
            Logger.info(f'Attempt {attempt + 1}: Fetching product data from {url} using proxy {random_proxy}')

            response = requests.get(
                url,
                headers=get_random_headers(),
                cookies={},
                proxies=random_proxy,
                timeout=10,
                verify=True
            )
            response.raise_for_status()

            # Parse the page content
            soup = BeautifulSoup(response.content, 'html.parser')

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

            spec_items = soup.find_all(class_='product-add-to-cart__specifications-item')

            # Find the specific item containing product code
            product_code = None
            for item in spec_items:
                if 'Product code:' in item.text:
                    product_code = item.text.strip().split('Product code:')[1].strip()
                    break

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
