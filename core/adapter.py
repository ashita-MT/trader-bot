class InteractionMessage:
    def __init__(self, interaction, api):
        self._interaction = interaction
        self._api = api
        self.author = self._Author(interaction)
        self.content = interaction.data.resolved.button_data if interaction.data and interaction.data.resolved else ""

    class _Author:
        def __init__(self, interaction):
            self.id = interaction.user_openid or interaction.group_member_openid or ""
            self.user_openid = interaction.user_openid or ""
            self.member_openid = interaction.group_member_openid or ""
            self.username = ""

    async def reply(self, **kwargs):
        content = kwargs.get("content", "")
        if self._interaction.group_openid:
            await self._api.post_group_message(
                group_openid=self._interaction.group_openid,
                msg_type=0,
                content=content,
            )
        elif self._interaction.user_openid:
            await self._api.post_c2c_message(
                openid=self._interaction.user_openid,
                msg_type=0,
                content=content,
            )
