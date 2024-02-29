from attrs import define, field, validators

from logprep.abc.credentials import Credentials


@define(kw_only=True)
class BasicAuthCredentials(Credentials):

    username: str = field(validator=validators.instance_of(str))
    password: str = field(validator=validators.instance_of(str))

    def authenticate(self):
        raise NotImplementedError
