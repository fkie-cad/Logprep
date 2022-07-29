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
        if not any([i in ssl_config for i in ssl_keys]):
            return

        cafile = ssl_config["cafile"] if "cafile" in ssl_config else None
        certfile = ssl_config["certfile"] if "certfile" in ssl_config else None
        keyfile = ssl_config["keyfile"] if "keyfile" in ssl_config else None
        password = ssl_config["password"] if "password" in ssl_config else None

        kafka.set_ssl_config(cafile, certfile, keyfile, password)

    @staticmethod
    def _set_if_exists(key: str, config: dict, kafka_setter):
        if key in config:
            kafka_setter(config[key])

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
        """Set configuration options for kafka.

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
        connector_type_cfg = self._config.get(connector_type, {})
        new_consumer_options = new_options.get(connector_type, {})
        if isinstance(new_consumer_options, dict):
            for key in new_consumer_options:
                if key not in connector_type_cfg:
                    raise UnknownOptionError(f"Unknown Option: {key}")
                connector_type_cfg[key] = new_consumer_options[key]

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
