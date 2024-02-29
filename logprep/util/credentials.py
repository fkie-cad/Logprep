from attrs import define, field, validators

from logprep.abc.credentials import Credentials


@define(kw_only=True)
class BasicAuthCredentials(Credentials):

    username: str = field(validator=validators.instance_of(str))
    password: str = field(validator=validators.instance_of(str))

    def authenticate(self):
        raise NotImplementedError


@define(kw_only=True)
class OAuth2TokenCredentials(Credentials):

    token: str = field(validator=validators.instance_of(str))

    def authenticate(self):
        raise NotImplementedError


class OAuth2PasswordFlowCredentials(OAuth2TokenCredentials):
    pass


class Oauth2ClientFlowCredentials(OAuth2TokenCredentials):
    pass
