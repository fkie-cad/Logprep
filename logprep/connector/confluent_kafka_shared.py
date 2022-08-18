"""This module contains functionality that allows to establish a connection with kafka."""


class ConfluentKafkaError(BaseException):
    """Base class for ConfluentKafka related exceptions."""


class UnknownOptionError(ConfluentKafkaError):
    """Raise if an invalid option has been set in the ConfluentKafka configuration."""


class InvalidMessageError(ConfluentKafkaError):
    """Raise if an invalid message has been received by ConfluentKafka."""


class ConfluentKafkaFactory:
    """Create ConfluentKafka connectors for logprep and input/output communication."""

    @staticmethod
    def _set_ssl_options(kafka: "ConfluentKafka", ssl_config: dict):
        ssl_keys = ["cafile", "certfile", "keyfile", "password"]
        if all(i in ssl_config for i in ssl_keys):
            cafile = ssl_config["cafile"]
            certfile = ssl_config["certfile"]
            keyfile = ssl_config["keyfile"]
            password = ssl_config["password"]
            kafka.set_ssl_config(cafile, certfile, keyfile, password)

    @staticmethod
    def _remove_shared_base_options(config):
        del config["type"]
        del config["bootstrapservers"]
        if "ssl" in config:
            del config["ssl"]


class ConfluentKafka:
    """A kafka connector that serves as both input and output connector."""

    def __init__(self, bootstrap_servers):
        self._bootstrap_servers = bootstrap_servers
        self._config = {
            "ssl": {"cafile": None, "certfile": None, "keyfile": None, "password": None}
        }

    def set_option(self, new_options: dict, connector_type: str):
        """Set configuration options for specified kafka connector type.

        Parameters
        ----------
        new_options : dict
           New options to set.
        connector_type : str
           Name of the connector type. Can be either producer or consumer.

        Raises
        ------
        UnknownOptionError
            Raises if an option is invalid.

        """
        default_connector_options = self._config.get(connector_type, {})
        new_connector_options = new_options.get(connector_type, {})
        self._set_connector_type_options(new_connector_options, default_connector_options)

    def _set_connector_type_options(self, user_options, default_options):
        """Iterate recursively over the default options and set the values from the user options."""
        both_options_are_numbers = isinstance(user_options, (int, float)) and isinstance(
            default_options, (int, float)
        )
        options_have_same_type = isinstance(user_options, type(default_options))

        if not options_have_same_type and not both_options_are_numbers:
            raise UnknownOptionError(
                f"Wrong Option type for '{user_options}'. "
                f"Got {type(user_options)}, expected {type(default_options)}."
            )
        if not isinstance(default_options, dict):
            return user_options
        for user_option in user_options:
            if user_option not in default_options:
                raise UnknownOptionError(f"Unknown Option: {user_option}")
            default_options[user_option] = self._set_connector_type_options(
                user_options[user_option], default_options[user_option]
            )
        return default_options

    def set_ssl_config(self, cafile: str, certfile: str, keyfile: str, password: str):
        """Set SSL configuration for kafka.

        Parameters
        ----------
        cafile : str
           Path to certificate authority file.
        certfile : str
           Path to certificate file.
        keyfile : str
           Path to private key file.
        password : str
           Password for private key.

        """
        self._config["ssl"]["cafile"] = cafile
        self._config["ssl"]["certfile"] = certfile
        self._config["ssl"]["keyfile"] = keyfile
        self._config["ssl"]["password"] = password

    @staticmethod
    def _format_message(error: BaseException) -> str:
        return (
            "{}: {}".format(type(error).__name__, str(error))
            if str(error)
            else type(error).__name__
        )

    def _set_base_confluent_settings(self, configuration):
        configuration["bootstrap.servers"] = ",".join(self._bootstrap_servers)
        if [self._config["ssl"][key] for key in self._config["ssl"]] != [None, None, None, None]:
            configuration.update(
                {
                    "security.protocol": "SSL",
                    "ssl.ca.location": self._config["ssl"]["cafile"],
                    "ssl.certificate.location": self._config["ssl"]["certfile"],
                    "ssl.key.location": self._config["ssl"]["keyfile"],
                    "ssl.key.password": self._config["ssl"]["password"],
                }
            )
