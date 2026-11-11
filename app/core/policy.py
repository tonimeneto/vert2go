from app.core.contracts import EngineError, Scope


class Policy:
    def __init__(self, config):
        self.config = config

    def identify(self, scope):
        if (not isinstance(scope, Scope) or scope.environment_id != self.config.environment_id
                or scope.channel != ('telegram' if self.config.telegram else 'local')
                or scope.chat_type != 'private' or type(scope.channel_user_id) is not int
                or type(scope.chat_id) is not int):
            raise EngineError('unauthorized')
        for user in self.config.users:
            if (user.enabled and user.channel == scope.channel and user.channel_user_id == scope.channel_user_id
                    and scope.chat_id in user.chat_ids):
                return user.role
        raise EngineError('unauthorized')

    def authorize(self, scope, permission):
        role = self.identify(scope)
        if permission not in self.config.permissions[role]:
            raise EngineError('unauthorized')
        return role
