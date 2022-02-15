import discord

def _proper_overwrites_mapping(overwrites):
    # idt we need member overwrites in backup tbh
    return {k.name: v for k, v in overwrites if not isinstance(k, discord.Member)}


def _overwrite_mapping_from_json(json: dict):
    return {k: discord.PermissionOverwrite(**v) for k, v in json.items()}
    

def _overwrite_mapping_json(permissions: dict):
    return {k: {key: value for key, value in v} for k, v in permissions.items()}

def valid_role_for_template(role: discord.Role):
    return all(
        [not role.is_bot_managed(), not role.is_default(), not role.is_integration(), not role.managed, not role.is_premium_subscriber()]
    )