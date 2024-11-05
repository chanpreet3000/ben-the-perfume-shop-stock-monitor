import os

import discord
from discord import app_commands
from Logger import Logger
from dotenv import load_dotenv
from discord.ext import tasks
from DatabaseManager import DatabaseManager

from utils import fetch_product_data
from watch_stock_cron import watch_stock_cron

load_dotenv()

watch_product_cron_delay_seconds = int(os.getenv('WATCH_PRODUCT_CRON_DELAY_SECONDS', 60 * 60))  # 1 hour


class Bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.db = DatabaseManager()

    async def setup_hook(self):
        await self.tree.sync()
        Logger.info("Command tree synced")


client = Bot()


@client.tree.command(name="tps-add-product", description="Add a product URL to watch")
async def add_product(interaction: discord.Interaction, url: str):
    Logger.info(f"Received add product request for URL: {url}")
    await interaction.response.defer(thinking=True)

    try:
        embed, product_data = await fetch_product_data(url, max_retries=5)
        if product_data is None:
            await interaction.followup.send(
                content="❌ Failed to fetch product data. Please make sure the URL is correct or try again."
            )
            return
        if client.db.add_watch_product(url):
            embed = discord.Embed(
                title="✅ Product Added",
                description=f"Started watching product: {url}",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="⚠️ Already Watching",
                description=f"This product is already being watched: {url}",
                color=0xffcc00
            )
    except Exception as e:
        Logger.error(f'Error adding product: {url}', e)
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred while adding the product.\n{str(e)}",
            color=0xff0000
        )

    await interaction.followup.send(embed=embed)


@client.tree.command(name="tps-remove-product", description="Remove a product URL from watch list")
async def remove_product(interaction: discord.Interaction, product_url: str):
    Logger.info(f"Received remove product request for URL: {product_url}")
    await interaction.response.defer(thinking=True)

    try:
        if client.db.remove_watch_product(product_url):
            embed = discord.Embed(
                title="✅ Product Removed",
                description=f"Stopped watching product: {product_url}",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="⚠️ Not Found",
                description=f"This product was not being watched: {product_url}",
                color=0xffcc00
            )
    except Exception as e:
        Logger.error('Error removing product:', e)
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred while removing the product.\n{str(e)}",
            color=0xff0000
        )

    await interaction.followup.send(embed=embed)


@client.tree.command(name="tps-list-products", description="Show all watched product URLs")
async def list_products(interaction: discord.Interaction):
    Logger.info("Received list products request")
    await interaction.response.defer(thinking=True)

    try:
        products = client.db.get_all_watch_products()
        if products:
            product_list = "\n".join([f"{i + 1}. {url}" for i, url in enumerate(products)])
            embed = discord.Embed(
                title="📋 Watched Products",
                description=product_list,
                color=0x00ccff
            )
        else:
            embed = discord.Embed(
                title="📋 Watched Products",
                description="No products are currently being watched.",
                color=0xffcc00
            )
    except Exception as e:
        Logger.error('Error listing products:', e)
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred while fetching the product list.\n{str(e)}",
            color=0xff0000
        )

    await interaction.followup.send(embed=embed)


@client.tree.command(name="tps-add-channel", description="Add a notification channel")
@app_commands.checks.has_permissions(administrator=True)
async def add_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    Logger.info(f"Received add channel request for channel ID: {channel.id}")
    await interaction.response.defer(thinking=True)

    try:
        if client.db.add_discord_channel(str(channel.id)):
            embed = discord.Embed(
                title="✅ Channel Added",
                description=f"Added {channel.mention} to notification channels.",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="⚠️ Already Added",
                description=f"{channel.mention} is already a notification channel.",
                color=0xffcc00
            )
    except Exception as e:
        Logger.error('Error adding channel:', e)
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred while adding the channel.\n{str(e)}",
            color=0xff0000
        )

    await interaction.followup.send(embed=embed)


@client.tree.command(name="tps-remove-channel", description="Remove a notification channel")
@app_commands.checks.has_permissions(administrator=True)
async def remove_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    Logger.info(f"Received remove channel request for channel ID: {channel.id}")
    await interaction.response.defer(thinking=True)

    try:
        if client.db.remove_discord_channel(str(channel.id)):
            embed = discord.Embed(
                title="✅ Channel Removed",
                description=f"Removed {channel.mention} from notification channels.",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="⚠️ Not Found",
                description=f"{channel.mention} was not a notification channel.",
                color=0xffcc00
            )
    except Exception as e:
        Logger.error('Error removing channel:', e)
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred while removing the channel.\n{str(e)}",
            color=0xff0000
        )

    await interaction.followup.send(embed=embed)


@client.tree.command(name="tps-list-channels", description="Show all notification channels")
async def list_channels(interaction: discord.Interaction):
    Logger.info("Received list channels request")
    await interaction.response.defer(thinking=True)

    try:
        channels = client.db.get_all_notification_channels()
        if channels:
            channel_mentions = []
            for channel_id in channels:
                channel = client.get_channel(int(channel_id))
                if channel:
                    channel_mentions.append(f"• {channel.mention}")
                else:
                    channel_mentions.append(f"• Unknown Channel (ID: {channel_id})")

            embed = discord.Embed(
                title="📋 Notification Channels",
                description="\n".join(channel_mentions),
                color=0x00ccff
            )
        else:
            embed = discord.Embed(
                title="📋 Notification Channels",
                description="No notification channels are configured.",
                color=0xffcc00
            )
    except Exception as e:
        Logger.error('Error listing channels:', e)
        embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred while fetching the channel list.\n{str(e)}",
            color=0xff0000
        )

    await interaction.followup.send(embed=embed)


@client.tree.command(name="tps-check-stock", description="Check the stock level of a product on theperfumeshop.com")
async def check_stock(interaction: discord.Interaction, product_url: str):
    Logger.info(f"Received check stock request {product_url}")
    await interaction.response.defer()

    try:
        embed, product = await fetch_product_data(product_url, max_retries=5)

        if product is None:
            await interaction.followup.send(
                content="❌ Failed to fetch product data. Please make sure the URL is correct or try again."
            )
            return

        await interaction.followup.send(
            content="🔍 Stock Check Result Completed",
            embed=embed
        )
        Logger.info(f'Finished checking stock for product {product_url}')
    except Exception as e:
        Logger.error('Error checking stock:', e)
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred while checking the product stock.\n{str(e)}",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed)


@tasks.loop(seconds=watch_product_cron_delay_seconds)
async def watched_products_stock_cron():
    Logger.info("Starting scheduled stock check")
    await watch_stock_cron(client)
    Logger.info(f"Scheduled stock check completed. Next run in {watch_product_cron_delay_seconds} seconds.")


@client.event
async def on_ready():
    Logger.info(f"Bot is ready and logged in as {client.user}")
    watched_products_stock_cron.start()


def run_bot():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        raise ValueError("Discord bot token not found in environment variables")

    Logger.info("Starting bot...")
    client.run(token)
