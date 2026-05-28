def get_user_id(message):
    author = message.author
    if hasattr(author, "id") and author.id:
        return author.id
    if hasattr(author, "user_openid") and author.user_openid:
        return author.user_openid
    if hasattr(author, "member_openid") and author.member_openid:
        return author.member_openid
    return "unknown"


class MentionMessage:
    """Wraps a message object to automatically @mention the user on reply."""
    def __init__(self, message, uid):
        object.__setattr__(self, '_message', message)
        object.__setattr__(self, '_uid', uid)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_message'), name)

    async def reply(self, **kwargs):
        content = kwargs.get('content', '')
        uid = object.__getattribute__(self, '_uid')
        kwargs['content'] = f"<@{uid}> {content}"
        return await object.__getattribute__(self, '_message').reply(**kwargs)
