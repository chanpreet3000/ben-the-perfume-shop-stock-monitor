from Logger import Logger
from discord_bot import run_bot
from DatabaseManager import DatabaseManager

if __name__ == "__main__":
    db = DatabaseManager()
    try:
        run_bot()
    except Exception as e:
        Logger.critical('Internal error occurred', e)
    finally:
        db.close()
        Logger.critical('Shutting down bot...')
