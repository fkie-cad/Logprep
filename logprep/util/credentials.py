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

    token: list[str] = field(factory=list)

    def authenticate(self):
        raise NotImplementedError


@define(kw_only=True)
class OAuth2PasswordFlowCredentials(OAuth2TokenCredentials):

    endpoint: str = field(validator=validators.instance_of(str))
    grand_type: str = field(validator=validators.instance_of(str))
    password: str = field(validator=validators.instance_of(str))
    username: str = field(validator=validators.instance_of(str))
    token: []

    def authenticate(self):
        raise NotImplementedError


@define(kw_only=True)
class OAuth2ClientFlowCredentials(OAuth2TokenCredentials):

    endpoint: str = field(validator=validators.instance_of(str))
    client_id: str = field(validator=validators.instance_of(str))
    client_secret: str = field(validator=validators.instance_of(str))
    token: []

    def authenticate(self):
        raise NotImplementedError
