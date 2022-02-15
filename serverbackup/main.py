import discord
from redbot.core import Config, commands
from redbot.core.bot import Red

class ServerBackup(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        
        self.config = Config.get_conf(self, 987654321, force_registration=True)
        
        self.config.init_custom("BACKUP", 1)
        
    # TODO
    # make commands to scroll through backups
    # delete backups
    # restore backups
    # make a backup of the current server