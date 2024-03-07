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

    endpoint: str = field(validator=validators.instance_of(str))
    token: str = field(validator=validators.instance_of(str))

    def authenticate(self):
        raise NotImplementedError


@define(kw_only=True)
class OAuth2PasswordFlowCredentials(OAuth2TokenCredentials):

    password: str = field(validator=validators.instance_of(str))
    username: str = field(validator=validators.instance_of(str))

    def authenticate(self):
        raise NotImplementedError


@define(kw_only=True)
class OAuth2ClientFlowCredentials(OAuth2TokenCredentials):

    client_id: str = field(validator=validators.instance_of(str))
    client_secret: str = field(validator=validators.instance_of(str))

    def authenticate(self):
        raise NotImplementedError
