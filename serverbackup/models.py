import datetime
from io import BytesIO
import secrets
from typing import Dict, Optional, Union
import aiohttp
import discord

from .utils import _proper_overwrites_mapping, _overwrite_mapping_from_json, _overwrite_mapping_json, valid_role_for_template

class Template:
    def __init__(self, **kwargs) -> None:
        self.id = kwargs.get('id') or secrets.token_urlsafe(5)
        self.created_at: datetime.datetime = kwargs.get('created_at') or datetime.datetime.now()
        self.original_guild_id: int = kwargs.get('original_guild_id')
        self.owner: int = kwargs.get('owner')
        self.uses: int = kwargs.get('uses') or 0
        self._roles: list[TemplateRole] = kwargs.get('roles', [])
        self._channels: list[Union[TemplateCategory, TemplateChannel]] = kwargs.get('channels', [])
        
    @staticmethod
    def verify_json(json: dict):
        return all(key in json for key in ["id", "roles", "channels", "original_guild_id"])
    
    @staticmethod
    def get_proper_overwrites_with_roles(roles: Dict[str, discord.Role], overwrites: Dict[str, discord.PermissionOverwrite]):
        return {roles[name]: ow for name, ow in overwrites.items() if name in roles}
    
    @property
    def json(self):
        return {
            "id": self.id,
            "created_at": self.created_at.timestamp(),
            "original_guild_id": self.original_guild_id,
            "owner": self.owner,
            "uses": self.uses,
            "roles": [role.json for role in self.roles],
            "channels": [channel.json for channel in self._channels],
        }
        
    @property
    def roles(self):
        return sorted(self._roles, key=lambda role: role.position, reverse=True)
    
    @property
    def channels(self):
        return (
            sorted([i for i in self._channels if isinstance(i, TemplateCategory)], key=lambda channel: channel.position, reverse=True),
            sorted([i for i in self._channels if isinstance(i, TemplateChannel)], key=lambda channel: channel.position, reverse=True)
            )
        
    async def apply_to_guild(self, guild: discord.Guild):
        reason = "Applying backup on server."
        [await role.delete(reason=reason) for role in guild.roles if valid_role_for_template(role)]
        [await category.delete(reason=reason) for category in guild.categories]
        [await channel.delete(reason=reason) for channel in guild.channels]
        
        created_roles = {}
        
        for role in self.roles:
            created_roles[role.name] = await guild.create_role(
                reason=reason,
                colour=role.colour,
                hoist=role.hoist,
                mentionable=role.mentionable,
                name=role.name,
                permissions=role.permissions
            )
            
        role = await guild.create_role(reason=reason, name=guild.me.name, permissions=discord.Permissions(administrator=True))
        await guild.me.add_roles(role)
            
        categories, channels = self.channels
        
            
        for category in categories:
            cat = await guild.create_category(
                name=category.name,
                overwrites=self.get_proper_overwrites_with_roles(created_roles, category.permissions),
                reason=reason,
                position=category.position
            )
            
                
            for child in category.children:
                perms = self.get_proper_overwrites_with_roles(created_roles, child.permissions)
                if child.type is discord.ChannelType.voice:
                    await cat.create_voice_channel(name=child.name, overwrites=perms, reason=reason)
                    
                elif child.type is discord.ChannelType.text:
                    act_chan: discord.TextChannel = await cat.create_text_channel(name=child.name, overwrites=perms, reason=reason, position=child.position, topic=child.topic)
                    if child.last_messages:
                        wh = await act_chan.create_webhook(name="new_webhook")
                        for msg in child.last_messages:
                            await wh.send(content=msg.content + "\n".join(msg.attachments), embeds=msg.embeds, avatar_url=msg.author_avatar_url, username=msg.author)
                    
                        
        for channel in channels:
            perms = self.get_proper_overwrites_with_roles(created_roles, channel.permissions)
            if channel.type is discord.ChannelType.voice:
                await guild.create_voice_channel(name=channel.name, overwrites=perms, reason=reason)
                    
            elif channel.type is discord.ChannelType.text:
                act_chan = await guild.create_text_channel(name=channel.name, overwrites=perms, reason=reason, position=channel.position, topic=channel.topic)
                if child.last_messages:
                    wh = await act_chan.create_webhook(name="new_webhook")
                    for msg in child.last_messages:
                        await wh.edit(name=msg.author, avatar=await msg.avatar)
                        await wh.send(content=msg.content + "\n".join(msg.attachments), embeds=msg.embeds)
                        
            await act_chan.send("Backup Restored.")
                
        
    @classmethod
    def from_json(cls, json: dict):
        if not cls.verify_json(json):
            raise ValueError("Invalid json for Template")
        
        json["created_at"] = datetime.datetime.fromtimestamp(json["created_at"])
        json["roles"] = [TemplateRole.from_json(role) for role in json["roles"]]
        json["channels"] = [TemplateChannel.from_json(channel) if channel.get("children") is None else TemplateCategory.from_json(channel) for channel in json["channels"]]
        
        return cls(**json)
    
    @classmethod
    async def from_guild(cls, guild: discord.Guild, owner: discord.Member):
        attrs = {
            "id": None,
            "original_guild_id": guild.id,
            "roles": [],
            "channels": [],
        }
        
        for role in guild.roles:
            if valid_role_for_template(role):
                attrs["roles"].append(TemplateRole.from_role(role))
            
        categories: Dict[str, TemplateCategory] = {}
        channels = []
        for channel in guild.channels:
            if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                continue
            if channel.category:
                if not categories.get(channel.category.name):
                    categories[channel.category.name] = await TemplateCategory.from_category(channel.category)
                    
                continue
            
            channels.append(await TemplateChannel.from_channel(channel))
            
        attrs["channels"] = [category for category in categories.values()] + channels
        attrs["owner"] = owner.id
        
        return cls(**attrs)
    
class TemplateCategory:
    def __init__(self, **kwargs) -> None:
        self.name: str = kwargs.get('name', 'New Category')
        self.position: int = kwargs.get('position', 0)
        self._children: list[TemplateChannel] = kwargs.get('children', [])
        self.permissions: Dict[str, discord.PermissionOverwrite] = kwargs.get('permissions', [])

    @staticmethod
    def verify_json(json: dict):
        return all(key in json for key in ['name', 'children', 'permissions'])

    @property
    def json(self):
        return {
            "name": self.name,
            "children": [c.json for c in self.children],
            "permissions": _overwrite_mapping_json(self.permissions)
        }
        
    @property
    def children(self):
        return sorted(self._children, key=lambda c: c.position)
        
    @classmethod
    def from_json(cls, json: dict):
        if not cls.verify_json(json):
            raise ValueError("Invalid json for TemplateCategory")
        
        json["children"] = [TemplateChannel.from_json(c) for c in json["children"]]
        json["permissions"] = _overwrite_mapping_from_json(json["permissions"])
        
        return cls(**json)
    
    @classmethod
    async def from_category(cls, category: discord.CategoryChannel):
        self = cls(
            name=category.name,
            children=[await TemplateChannel.from_channel(c) for c in category.channels],
            permissions=_proper_overwrites_mapping(category.overwrites)
        )
        
        return self

class TemplateChannel:
    def __init__(self, **kwargs) -> None:
        self.name: str = kwargs.get('name', "default channel name")
        self.topic: str = kwargs.get('topic', "")
        self.type: discord.ChannelType = kwargs.get('type', discord.ChannelType.text)
        self.permissions: Dict[str, discord.PermissionOverwrite] = kwargs.get("permissions", {})
        self.position: int = kwargs.get("position", 0)
        self.category: TemplateCategory = kwargs.get("category", None)
        self.last_messages: list[TemplateMessage] = kwargs.get("last_messages", [])
        
    @staticmethod
    def verify_json(json: dict):
        return all(k in json for k in ['name', "topic", "type", 'permissions', 'position'])
    
    @property
    def json(self):
        return {
            "name": self.name,
            "topic": self.topic,
            "type": self.type.name,
            "permissions": _overwrite_mapping_json(self.permissions),
            "position": self.position,
            "last_messages": [m.json for m in self.last_messages]
        }
        
    @classmethod
    def from_json(cls, json: dict):
        if not cls.verify_json(json):
            raise ValueError("Invalid json for template channel.")
        
        json["type"] = discord.ChannelType[json["type"]]
        json["permissions"] = _overwrite_mapping_from_json(json["permissions"])
        json["last_messages"] = [TemplateMessage.from_json(m) for m in json["last_messages"]]
        
        return cls(**json)
    
    @classmethod
    async def from_channel(cls, channel: Union[discord.TextChannel, discord.VoiceChannel]):
        last_messages = []
        if type(channel) is discord.TextChannel:
            async for msg in channel.history(limit=3):
                last_messages.insert(0, TemplateMessage.from_message(msg)) 
                # so that messages aren't in reversed order lol
        attrs = {
            "name": channel.name,
            "topic": getattr(channel, "topic", None),
            "type": channel.type,
            "permissions": _proper_overwrites_mapping(channel.overwrites),
            "position": channel.position,
            "last_messages": last_messages
        }
        return cls(**attrs)
    
class TemplateMessage:
    def __init__(self, **kwargs) -> None:
        self.author: str = kwargs.get("author", "default author") # author name with discrim only
        self.author_avatar_url: Optional[str] = kwargs.get("author_avatar_url") # the avatar url, if available
        self.content: str = kwargs.get("content") # content of the message
        self.embeds: list[discord.Embed] = kwargs.get("embeds", []) # embeds of the message
        self.attachments: list[str] = kwargs.get("attachments", []) # we will only be saving urls of the attachments for this
        
    @property
    def json(self):
        return {
            "author": self.author,
            "author_avatar_url": self.author_avatar_url,
            "content": self.content,
            "embeds": [e.to_dict() for e in self.embeds],
            "attachments": self.attachments
        }
        
    @property
    def avatar(self):
        return self.get_avatar_bytes(self.author_avatar_url)
        
    @staticmethod
    async def get_avatar_bytes(avatar_url):
        async with aiohttp.request("GET", avatar_url) as resp:
            avatar = BytesIO(await resp.read())
            return avatar
        
    @staticmethod
    def verify_json(json: dict):
        return all(k in json for k in ['author', 'author_avatar_url', 'content', 'embeds', 'attachments'])
        
    @classmethod
    def from_json(cls, json: dict):
        if not cls.verify_json(json):
            raise ValueError("Invalid json for template message.")
        
        json["embeds"] = [discord.Embed.from_dict(e) for e in json["embeds"]]
        
        return cls(**json)
    
    @classmethod
    def from_message(cls, message: discord.Message):
        attrs = {
            "author": str(message.author),
            "author_avatar_url": str(message.author.avatar_url),
            "content": message.content,
            "embeds": message.embeds,
            "attachments": [str(a.url) for a in message.attachments]
        }
        return cls(**attrs)
    
class TemplateRole:
    def __init__(self, **kwargs) -> None:
        self.name: str = kwargs.get("name", "default role name")
        self.color: discord.Color = kwargs.get("color", discord.Color.default())
        self.hoist: bool = kwargs.get("hoist", False)
        self.permissions: discord.Permissions = kwargs.get("permissions", discord.Permissions.none())
        self.mentionable: bool = kwargs.get("mentionable", False)
        self.is_everyone: bool = kwargs.get("is_everyone", False)
        self.position: int = kwargs.get("position")
        
    @property
    def json(self):
        return {
            "name": self.name,
            "color": self.color.value,
            "hoist": self.hoist,
            "permissions": self.permissions.value,
            "mentionable": self.mentionable,
            "is_everyone": self.is_everyone,
            "position": self.position
        }
        
    @property
    def colour(self):
        return self.color
        
    @staticmethod
    def verify_json(json: dict):
        return all(k in json for k in ['name', 'color', 'hoist', 'permissions', 'mentionable', 'is_everyone', 'position'])
        
    @classmethod
    def from_json(cls, json: dict):
        if not cls.verify_json(json):
            raise ValueError("Invalid json for template message.")
        
        json["color"] = discord.Color(json["color"])
        json["permissions"] = discord.Permissions(json["permissions"])
        
        return cls(**json)
    
    @classmethod
    def from_role(cls, role: discord.Role):
        attrs = {
            "name": role.name,
            "color": role.color,
            "hoist": role.hoist,
            "permissions": role.permissions,
            "mentionable": role.mentionable,
            "is_everyone": role.id == role.guild.id,
            "position": role.position
        }
        
        return cls(**attrs)
