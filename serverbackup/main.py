import datetime
import logging
import discord
from redbot.core import Config, commands
from redbot.core.bot import Red
from .models import Template

log = logging.getLogger("red.vcraycogs.serverbackup")

class ServerBackup(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        
        self.config = Config.get_conf(self, 987654321, force_registration=True)
        self.config.register_guild(last_use=None, last_backup=None)
        
        self.config.init_custom("BACKUP", 1)
        
    # TODO
    # make commands to scroll through backups
    # delete backups
    # restore backups
    # make a backup of the current server
    
    async def get_all_templates(self):
        templates = await self.config.custom("BACKUP").all()
        templates = [Template.from_json(template) for id, template in templates.items()]
        return templates
    
    def greater_than_7_days(self, timestamp: int):
        date = datetime.datetime.fromtimestamp(timestamp)
        return (datetime.datetime.now() - date).days > 7
    
    @commands.group(name="backup", cooldown_after_parsing=True)
    @commands.admin_or_permissions(administrator=True)
    async def backup(self, ctx: commands.Context):
        """
        Backup commands
        """
        pass
    
    @backup.command(name="create")
    @commands.cooldown(1, 60*60*24, commands.BucketType.guild)
    async def backup_create(self, ctx: commands.Context):
        """
        Create a backup of the current server
        """
        if (timestamp:=await self.config.guild(ctx.guild).last_backup()) and self.greater_than_7_days(timestamp):
            return await ctx.send("You can only create one backup every 7 days")
        
        await ctx.send("Creating backup. This can take a while.")
        async with ctx.typing():
            try:
                template = await Template.from_guild(ctx.guild, ctx.author)
                json = template.json
                await self.config.custom("BACKUP", template.id).set(json)
                await ctx.send("Backup created and saved with the id: `{}`".format(template.id))
            
            except Exception as e:
                log.exception("Error occurred while creating backup.", exc_info=e)
            
    @backup.command(name="list")
    async def backup_list(self, ctx: commands.Context):
        """
        List all backups
        """
        templates = await self.get_all_templates()
        if not templates:
            await ctx.send("No backups found.")
            return
        embed = discord.Embed(
            title="**Stored Server Backups**",
            description="\n\n".join(
                [
                    f"**{template.id}**\nCreated at: <t:{int(template.created_at.timestamp())}:R>"
                    f"\n{len(template._channels)} channels and {len(template._roles)} roles" 
                    for template in templates
                ]
            )
        )
        await ctx.send(embed=embed)
        
    @backup.command(name="delete")
    async def backup_delete(self, ctx: commands.Context, id: str):
        """
        Delete a backup.
        
        `id` is the template id which you can see with `backup list`
        """
        if not (temp:=(await self.config.custom("BACKUP").all()).get(id)):
            await ctx.send("Backup not found.")
            return
        
        if temp["owner"] != ctx.author.id:
            return await ctx.send("You can only delete your own backups and you do now own this backup.")
        
        await self.config.custom("BACKUP", id).clear()
        await ctx.send("Backup deleted.")
        
    @backup.command(name="restore")
    @commands.cooldown(1, 60*60*24, commands.BucketType.guild)
    async def backup_restore(self, ctx: commands.Context, id: str):
        """
        Restore a backup.
        
        `id` is the template id which you can see with `backup list`
        """
        if not (temp:=(await self.config.custom("BACKUP").all()).get(id)):
            await ctx.send("Backup not found.")
            return
        
        if (timestamp:=await self.config.guild(ctx.guild).last_use()) and self.greater_than_7_days(timestamp):
            return await ctx.send("You can only restore one backup every 7 days")
        
        template = Template.from_json(temp)
        await ctx.send("Restoring backup. This can take a while.")
        async with ctx.typing():
            await template.apply_to_guild(ctx.guild)
            template.uses += 1
            await self.config.custom("BACKUP", template.id).set(template.json)