"""
Normalizer
==========

The normalizer requires the additional field :code:`normalize`.
It contains key-value pairs that define if and how fields gets normalized.
The keys describe fields that are going to be normalized and the values describe the new normalized fields.
Through normalizing, old fields are being copied to new fields, but the old fields are not deleted.

In the following example the field :code:`event_data.ClientAddress` is normalized to :code:`client.ip`.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'event_data.ClientAddress'
    normalize:
      event_data.ClientAddress: client.ip
    description: '...'

Extraction and Replacement
--------------------------

Instead of copying a whole field, it is possible to copy only parts of it via regex capture groups.
These can be then extracted and rearranged in a new field.
The groups are defined in a configurable file as keywords and can be referenced from within the rules via the Python regex syntax.

Instead of specifying a target field, a list with three elements has to be used.
The first element is the target field, the second element is a regex keyword and the third field is a regex expression that defines how the value should be inserted into the new field.

In the following example :code:`event_data.address_text: "The IP is 1.2.3.4 and the port is 1234!"` is normalized to :code:`address: "1.2.3.4:1234"`.

..  code-block:: json
    :linenos:
    :caption: Example - Definition of regex keywords in the regex mapping file

    {
      "RE_IP_PORT_CAP": ".*(?P<IP>[\\d.]+).*(?P<PORT>\\d+).*",
      "RE_WHOLE_FIELD": "(.*)"
    }

..  code-block:: yaml
    :linenos:
    :caption: Example - Rule with extraction

        filter: event_id
        normalize:
          event_data.address_text:
          - address
          - RE_IP_PORT_CAP
          - '\g<IP>:\g<PORT>'

Grok
----

Grok functionality is fully supported for field normalization.
This can be combined with the normalizations that have been already introduced or it can be used
instead of them.
By combining both types of normalization it is possible to perform transformations on results of
Grok that can not be achieved by Grok alone.
All Grok normalizations are always performed before other normalizations.
An example for this is the creation of nested fields.

The following example would normalize
:code:`event_data.ip_and_port: "Linus has the address 1.2.3.4 1234", event_data.address_text: "This is an address: 1.2.3.4:1234"` to
:code:`address.ip: "1.2.3.4"`, :code:`address.port: 1234`, :code:`name: Linus` and
:code:`address.combined: 1.2.3.4 and 1234`.

..  code-block:: yaml
    :linenos:
    :caption: Example - Grok normalization and subsequent normalization of a result

      filter: event_id
      normalize:
        event_data.ip_and_port: '{"grok": "%{USER:name} has the address %{IP:[address][ip]} %{NUMBER:[address][port]:int}"}'
        event_data.address_text:
        - address.combined
        - RE_IP_PORT_CAP
        - '\g<IP> and \g<PORT>'

It is furthermore possible to use more than one Grok pattern for a field by specifying them
in a list.
The patterns will be sequentially checked until one of them matches.

The following example would normalize :code:`some_field_with_an_ip: "1.2.3.4 1234"` to
:code:`ip: "1.2.3.4"`, :code:`port: 1234`, skipping the first Grok pattern.
:code:`some_field_with_an_ip: "1.2.3.4 1234 foo"` would be however normalized to
:code:`ip_foo: "1.2.3.4"`, :code:`port_foo: 1234`.

..  code-block:: yaml
    :linenos:
    :caption: Example - Grok normalization with multiple patterns

      filter: 'some_field_with_an_ip'
      normalize:
        some_field_with_an_ip:
          grok:
            - '%{IP:ip_foo} %{NUMBER:port_foo:int} foo'
            - '%{IP:ip} %{NUMBER:port:int}'

As Grok pattern are only applied when they match a given input string it is sometimes desired to
know when none of the given pattern matches.
This is helpful in identifying new, unknown or reconfigured log sources that are not correctly covered by the current
rule set.
To activate the output of this information it is required to add the field
:code:`failure_target_field` to the grok rule.
This will describe the output field where the grok failure should be written to.
It can be a dotted field path.
An example rule would look like:

..  code-block:: yaml
    :linenos:
    :caption: Example - Grok normalization with grok failure target field

      filter: 'some_field_with_an_ip'
      normalize:
        some_field_with_an_ip:
          grok:
            - '%{IP:ip_foo} %{NUMBER:port_foo:int} foo'
            - '%{IP:ip} %{NUMBER:port:int}'
          failure_target_field: 'grok_failure'

If this is applied to an event which has the field :code:`some_field_with_an_ip`, but it's content
is not matched by any grok-filter then the :code:`grok_failure` field will be added.
This failure field will contain a subfield which identifies the grok target field as well as the
first 100 characters of the fields content.
By adding the failure information as a separate object it is possible to add more failures to it
in case many different grok rules exist and multiple events are not matched by any grok pattern.

Given this example event:

..  code-block:: json
    :linenos:
    :caption: Example Input Event

    {
      "some_field_with_an_ip": "content which is not an ip",
      "other event": "content"
    }

The normalizer would produce the following output event:

..  code-block:: json
    :linenos:
    :caption: Example Output Event

    {
      "some_field_with_an_ip": "content which is not an ip",
      "other event": "content",
      "grok_failure": {
        "some_field_with_an_ip": "content which is not an ip"
      }
    }

If the grok field is a subfield somewhere inside the event, then the keys of the grok_failure object
will contain the path to this subfield separated by :code:`>`.
This helps in identifying the original source field to which the grok pattern was applied to.
A grok failure output example would look like:

..  code-block:: json
    :linenos:
    :caption: Example Output Event

    {
      "nested_ip": {
        "some_field_with_an_ip": "content which is not an ip",
      },
      "other event": "content",
      "grok_failure": {
        "nested_ip>some_field_with_an_ip": "content which is not an ip"
      }
    }

Normalization of Timestamps
---------------------------

There is a special functionality that allows to normalize timestamps.
With this functionality different timestamp formats can be converted to ISO8601 and timezones can be adapted.
Instead of giving a target field, the special field `timestamp` is used.
Under this field additional configurations for the normalization can be specified.
Under `timestamp.source_formats` a list of possible source formats for the timestamp must be defined.
The original timezone of the timestamp must be specified in `timestamp.source_timezone`.
Furthermore, in `timestamp.destination_timezone` the new timestamp must be specified.
Finally, `timestamp.destination` defines the target field to which the new timestamp should be written.
Optionally, it can be defined if the normalization is allowed to override existing values by setting `timestamp.allow_override` to `true` or `false`.
It is allowed to override by default.

Valid formats for timestamps are defined by the notation of the Python datetime module.
Additionally, the value `ISO8601` and `UNIX` can be used for the `source_formats` field. The former can be used if the
timestamp already exists in the ISO98601 format, such that only a timezone conversion should be applied. And the latter
can be used if the timestamp is given in the UNIX Epoch Time. This supports the Unix timestamps in seconds and
milliseconds.

Valid timezones are defined in the pytz module:

.. raw:: html

   <details>
   <summary><a>List of all timezones</a></summary>

.. code-block:: text
   :linenos:
   :caption: Timezones from the Python pytz module

   Africa/Abidjan
   Africa/Accra
   Africa/Addis_Ababa
   Africa/Algiers
   Africa/Asmara
   Africa/Asmera
   Africa/Bamako
   Africa/Bangui
   Africa/Banjul
   Africa/Bissau
   Africa/Blantyre
   Africa/Brazzaville
   Africa/Bujumbura
   Africa/Cairo
   Africa/Casablanca
   Africa/Ceuta
   Africa/Conakry
   Africa/Dakar
   Africa/Dar_es_Salaam
   Africa/Djibouti
   Africa/Douala
   Africa/El_Aaiun
   Africa/Freetown
   Africa/Gaborone
   Africa/Harare
   Africa/Johannesburg
   Africa/Juba
   Africa/Kampala
   Africa/Khartoum
   Africa/Kigali
   Africa/Kinshasa
   Africa/Lagos
   Africa/Libreville
   Africa/Lome
   Africa/Luanda
   Africa/Lubumbashi
   Africa/Lusaka
   Africa/Malabo
   Africa/Maputo
   Africa/Maseru
   Africa/Mbabane
   Africa/Mogadishu
   Africa/Monrovia
   Africa/Nairobi
   Africa/Ndjamena
   Africa/Niamey
   Africa/Nouakchott
   Africa/Ouagadougou
   Africa/Porto-Novo
   Africa/Sao_Tome
   Africa/Timbuktu
   Africa/Tripoli
   Africa/Tunis
   Africa/Windhoek
   America/Adak
   America/Anchorage
   America/Anguilla
   America/Antigua
   America/Araguaina
   America/Argentina/Buenos_Aires
   America/Argentina/Catamarca
   America/Argentina/ComodRivadavia
   America/Argentina/Cordoba
   America/Argentina/Jujuy
   America/Argentina/La_Rioja
   America/Argentina/Mendoza
   America/Argentina/Rio_Gallegos
   America/Argentina/Salta
   America/Argentina/San_Juan
   America/Argentina/San_Luis
   America/Argentina/Tucuman
   America/Argentina/Ushuaia
   America/Aruba
   America/Asuncion
   America/Atikokan
   America/Atka
   America/Bahia
   America/Bahia_Banderas
   America/Barbados
   America/Belem
   America/Belize
   America/Blanc-Sablon
   America/Boa_Vista
   America/Bogota
   America/Boise
   America/Buenos_Aires
   America/Cambridge_Bay
   America/Campo_Grande
   America/Cancun
   America/Caracas
   America/Catamarca
   America/Cayenne
   America/Cayman
   America/Chicago
   America/Chihuahua
   America/Coral_Harbour
   America/Cordoba
   America/Costa_Rica
   America/Creston
   America/Cuiaba
   America/Curacao
   America/Danmarkshavn
   America/Dawson
   America/Dawson_Creek
   America/Denver
   America/Detroit
   America/Dominica
   America/Edmonton
   America/Eirunepe
   America/El_Salvador
   America/Ensenada
   America/Fort_Wayne
   America/Fortaleza
   America/Glace_Bay
   America/Godthab
   America/Goose_Bay
   America/Grand_Turk
   America/Grenada
   America/Guadeloupe
   America/Guatemala
   America/Guayaquil
   America/Guyana
   America/Halifax
   America/Havana
   America/Hermosillo
   America/Indiana/Indianapolis
   America/Indiana/Knox
   America/Indiana/Marengo
   America/Indiana/Petersburg
   America/Indiana/Tell_City
   America/Indiana/Vevay
   America/Indiana/Vincennes
   America/Indiana/Winamac
   America/Indianapolis
   America/Inuvik
   America/Iqaluit
   America/Jamaica
   America/Jujuy
   America/Juneau
   America/Kentucky/Louisville
   America/Kentucky/Monticello
   America/Knox_IN
   America/Kralendijk
   America/La_Paz
   America/Lima
   America/Los_Angeles
   America/Louisville
   America/Lower_Princes
   America/Maceio
   America/Managua
   America/Manaus
   America/Marigot
   America/Martinique
   America/Matamoros
   America/Mazatlan
   America/Mendoza
   America/Menominee
   America/Merida
   America/Metlakatla
   America/Mexico_City
   America/Miquelon
   America/Moncton
   America/Monterrey
   America/Montevideo
   America/Montreal
   America/Montserrat
   America/Nassau
   America/New_York
   America/Nipigon
   America/Nome
   America/Noronha
   America/North_Dakota/Beulah
   America/North_Dakota/Center
   America/North_Dakota/New_Salem
   America/Ojinaga
   America/Panama
   America/Pangnirtung
   America/Paramaribo
   America/Phoenix
   America/Port-au-Prince
   America/Port_of_Spain
   America/Porto_Acre
   America/Porto_Velho
   America/Puerto_Rico
   America/Rainy_River
   America/Rankin_Inlet
   America/Recife
   America/Regina
   America/Resolute
   America/Rio_Branco
   America/Rosario
   America/Santa_Isabel
   America/Santarem
   America/Santiago
   America/Santo_Domingo
   America/Sao_Paulo
   America/Scoresbysund
   America/Shiprock
   America/Sitka
   America/St_Barthelemy
   America/St_Johns
   America/St_Kitts
   America/St_Lucia
   America/St_Thomas
   America/St_Vincent
   America/Swift_Current
   America/Tegucigalpa
   America/Thule
   America/Thunder_Bay
   America/Tijuana
   America/Toronto
   America/Tortola
   America/Vancouver
   America/Virgin
   America/Whitehorse
   America/Winnipeg
   America/Yakutat
   America/Yellowknife
   Antarctica/Casey
   Antarctica/Davis
   Antarctica/DumontDUrville
   Antarctica/Macquarie
   Antarctica/Mawson
   Antarctica/McMurdo
   Antarctica/Palmer
   Antarctica/Rothera
   Antarctica/South_Pole
   Antarctica/Syowa
   Antarctica/Vostok
   Arctic/Longyearbyen
   Asia/Aden
   Asia/Almaty
   Asia/Amman
   Asia/Anadyr
   Asia/Aqtau
   Asia/Aqtobe
   Asia/Ashgabat
   Asia/Ashkhabad
   Asia/Baghdad
   Asia/Bahrain
   Asia/Baku
   Asia/Bangkok
   Asia/Beirut
   Asia/Bishkek
   Asia/Brunei
   Asia/Calcutta
   Asia/Choibalsan
   Asia/Chongqing
   Asia/Chungking
   Asia/Colombo
   Asia/Dacca
   Asia/Damascus
   Asia/Dhaka
   Asia/Dili
   Asia/Dubai
   Asia/Dushanbe
   Asia/Gaza
   Asia/Harbin
   Asia/Hebron
   Asia/Ho_Chi_Minh
   Asia/Hong_Kong
   Asia/Hovd
   Asia/Irkutsk
   Asia/Istanbul
   Asia/Jakarta
   Asia/Jayapura
   Asia/Jerusalem
   Asia/Kabul
   Asia/Kamchatka
   Asia/Karachi
   Asia/Kashgar
   Asia/Kathmandu
   Asia/Katmandu
   Asia/Kolkata
   Asia/Krasnoyarsk
   Asia/Kuala_Lumpur
   Asia/Kuching
   Asia/Kuwait
   Asia/Macao
   Asia/Macau
   Asia/Magadan
   Asia/Makassar
   Asia/Manila
   Asia/Muscat
   Asia/Nicosia
   Asia/Novokuznetsk
   Asia/Novosibirsk
   Asia/Omsk
   Asia/Oral
   Asia/Phnom_Penh
   Asia/Pontianak
   Asia/Pyongyang
   Asia/Qatar
   Asia/Qyzylorda
   Asia/Rangoon
   Asia/Riyadh
   Asia/Saigon
   Asia/Sakhalin
   Asia/Samarkand
   Asia/Seoul
   Asia/Shanghai
   Asia/Singapore
   Asia/Taipei
   Asia/Tashkent
   Asia/Tbilisi
   Asia/Tehran
   Asia/Tel_Aviv
   Asia/Thimbu
   Asia/Thimphu
   Asia/Tokyo
   Asia/Ujung_Pandang
   Asia/Ulaanbaatar
   Asia/Ulan_Bator
   Asia/Urumqi
   Asia/Vientiane
   Asia/Vladivostok
   Asia/Yakutsk
   Asia/Yekaterinburg
   Asia/Yerevan
   Atlantic/Azores
   Atlantic/Bermuda
   Atlantic/Canary
   Atlantic/Cape_Verde
   Atlantic/Faeroe
   Atlantic/Faroe
   Atlantic/Jan_Mayen
   Atlantic/Madeira
   Atlantic/Reykjavik
   Atlantic/South_Georgia
   Atlantic/St_Helena
   Atlantic/Stanley
   Australia/ACT
   Australia/Adelaide
   Australia/Brisbane
   Australia/Broken_Hill
   Australia/Canberra
   Australia/Currie
   Australia/Darwin
   Australia/Eucla
   Australia/Hobart
   Australia/LHI
   Australia/Lindeman
   Australia/Lord_Howe
   Australia/Melbourne
   Australia/NSW
   Australia/North
   Australia/Perth
   Australia/Queensland
   Australia/South
   Australia/Sydney
   Australia/Tasmania
   Australia/Victoria
   Australia/West
   Australia/Yancowinna
   Brazil/Acre
   Brazil/DeNoronha
   Brazil/East
   Brazil/West
   CET
   CST6CDT
   Canada/Atlantic
   Canada/Central
   Canada/East-Saskatchewan
   Canada/Eastern
   Canada/Mountain
   Canada/Newfoundland
   Canada/Pacific
   Canada/Saskatchewan
   Canada/Yukon
   Chile/Continental
   Chile/EasterIsland
   Cuba
   EET
   EST
   EST5EDT
   Egypt
   Eire
   Etc/GMT
   Etc/GMT+0
   Etc/GMT+1
   Etc/GMT+10
   Etc/GMT+11
   Etc/GMT+12
   Etc/GMT+2
   Etc/GMT+3
   Etc/GMT+4
   Etc/GMT+5
   Etc/GMT+6
   Etc/GMT+7
   Etc/GMT+8
   Etc/GMT+9
   Etc/GMT-0
   Etc/GMT-1
   Etc/GMT-10
   Etc/GMT-11
   Etc/GMT-12
   Etc/GMT-13
   Etc/GMT-14
   Etc/GMT-2
   Etc/GMT-3
   Etc/GMT-4
   Etc/GMT-5
   Etc/GMT-6
   Etc/GMT-7
   Etc/GMT-8
   Etc/GMT-9
   Etc/GMT0
   Etc/Greenwich
   Etc/UCT
   Etc/UTC
   Etc/Universal
   Etc/Zulu
   Europe/Amsterdam
   Europe/Andorra
   Europe/Athens
   Europe/Belfast
   Europe/Belgrade
   Europe/Berlin
   Europe/Bratislava
   Europe/Brussels
   Europe/Bucharest
   Europe/Budapest
   Europe/Chisinau
   Europe/Copenhagen
   Europe/Dublin
   Europe/Gibraltar
   Europe/Guernsey
   Europe/Helsinki
   Europe/Isle_of_Man
   Europe/Istanbul
   Europe/Jersey
   Europe/Kaliningrad
   Europe/Kiev
   Europe/Lisbon
   Europe/Ljubljana
   Europe/London
   Europe/Luxembourg
   Europe/Madrid
   Europe/Malta
   Europe/Mariehamn
   Europe/Minsk
   Europe/Monaco
   Europe/Moscow
   Europe/Nicosia
   Europe/Oslo
   Europe/Paris
   Europe/Podgorica
   Europe/Prague
   Europe/Riga
   Europe/Rome
   Europe/Samara
   Europe/San_Marino
   Europe/Sarajevo
   Europe/Simferopol
   Europe/Skopje
   Europe/Sofia
   Europe/Stockholm
   Europe/Tallinn
   Europe/Tirane
   Europe/Tiraspol
   Europe/Uzhgorod
   Europe/Vaduz
   Europe/Vatican
   Europe/Vienna
   Europe/Vilnius
   Europe/Volgograd
   Europe/Warsaw
   Europe/Zagreb
   Europe/Zaporozhye
   Europe/Zurich
   GB
   GB-Eire
   GMT
   GMT+0
   GMT-0
   GMT0
   Greenwich
   HST
   Hongkong
   Iceland
   Indian/Antananarivo
   Indian/Chagos
   Indian/Christmas
   Indian/Cocos
   Indian/Comoro
   Indian/Kerguelen
   Indian/Mahe
   Indian/Maldives
   Indian/Mauritius
   Indian/Mayotte
   Indian/Reunion
   Iran
   Israel
   Jamaica
   Japan
   Kwajalein
   Libya
   MET
   MST
   MST7MDT
   Mexico/BajaNorte
   Mexico/BajaSur
   Mexico/General
   NZ
   NZ-CHAT
   Navajo
   PRC
   PST8PDT
   Pacific/Apia
   Pacific/Auckland
   Pacific/Chatham
   Pacific/Chuuk
   Pacific/Easter
   Pacific/Efate
   Pacific/Enderbury
   Pacific/Fakaofo
   Pacific/Fiji
   Pacific/Funafuti
   Pacific/Galapagos
   Pacific/Gambier
   Pacific/Guadalcanal
   Pacific/Guam
   Pacific/Honolulu
   Pacific/Johnston
   Pacific/Kiritimati
   Pacific/Kosrae
   Pacific/Kwajalein
   Pacific/Majuro
   Pacific/Marquesas
   Pacific/Midway
   Pacific/Nauru
   Pacific/Niue
   Pacific/Norfolk
   Pacific/Noumea
   Pacific/Pago_Pago
   Pacific/Palau
   Pacific/Pitcairn
   Pacific/Pohnpei
   Pacific/Ponape
   Pacific/Port_Moresby
   Pacific/Rarotonga
   Pacific/Saipan
   Pacific/Samoa
   Pacific/Tahiti
   Pacific/Tarawa
   Pacific/Tongatapu
   Pacific/Truk
   Pacific/Wake
   Pacific/Wallis
   Pacific/Yap
   Poland
   Portugal
   ROC
   ROK
   Singapore
   Turkey
   UCT
   US/Alaska
   US/Aleutian
   US/Arizona
   US/Central
   US/East-Indiana
   US/Eastern
   US/Hawaii
   US/Indiana-Starke
   US/Michigan
   US/Mountain
   US/Pacific
   US/Pacific-New
   US/Samoa
   UTC
   Universal
   W-SU
   WET
   Zulu

.. raw:: html

   </details>
   <br/>

In the following example :code:`@timestamp: 2000 12 31 - 22:59:59` would be normalized to :code:`@timestamp: 2000-12-31T23:59:59+01:00`.

..  code-block:: yaml
    :linenos:
    :caption: Example - Normalization of a timestamp

    filter: '@timestamp'
    normalize:
      '@timestamp':
        timestamp:
          destination: '@timestamp'
          source_formats:
          - '%Y %m %d - %H:%M:%S'
          source_timezone: 'UTC'
          destination_timezone: 'Europe/Berlin'
    description: 'Test-rule with matching auto-test'

If Grok and a timestamp normalization is being used in the same rule, then Grok is being applied first,
so that a time normalization can be performed on the Grok results.
"""

import re
from typing import Union, Dict, List

from pygrok import Grok

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError

GROK_DELIMITER = "__________________"


class NormalizerRuleError(InvalidRuleDefinitionError):
    """Base class for Normalizer rule related exceptions."""

    def __init__(self, message):
        super().__init__(f"Normalizer rule ({message}): ")


class InvalidNormalizationDefinition(NormalizerRuleError):
    """Raise if normalization definition invalid."""

    def __init__(self, definition: Union[list, dict]):
        message = f"The following normalization definition is invalid: {definition}"
        super().__init__(message)


class InvalidGrokDefinition(NormalizerRuleError):
    """Raise if grok definition invalid."""

    def __init__(self, definition: Union[list, dict]):
        message = f"The following grok-expression is invalid: {definition}"
        super().__init__(message)


class InvalidTimestampDefinition(NormalizerRuleError):
    """Raise if timestamp definition invalid."""

    def __init__(self, definition: Union[list, dict]):
        message = f"The following timestamp normalization definition is invalid: {definition}"
        super().__init__(message)


class GrokWrapper:
    """Wrap around pygrok to add delimiter support."""

    grok_delimiter_pattern = re.compile(GROK_DELIMITER)

    def __init__(self, patterns: Union[str, List[str]], failure_target_field=None, **kwargs):
        if isinstance(patterns, str):
            self._grok_list = [Grok(f"^{patterns}$", **kwargs)]
        else:
            patterns = [f"^{pattern}$" for pattern in patterns]
            self._grok_list = [Grok(pattern_item, **kwargs) for pattern_item in patterns]

        self._match_cnt_initialized = False
        self.failure_target_field = failure_target_field

    def __eq__(self, other: "GrokWrapper") -> bool:
        return set([grok_item.regex_obj for grok_item in self._grok_list]) == set(
            [grok_item.regex_obj for grok_item in other._grok_list]
        )

    def match(self, text: str, pattern_matches: dict = None) -> Dict[str, str]:
        """Match string via grok using delimiter and count matches if enabled."""
        if pattern_matches is not None and not self._match_cnt_initialized:
            for grok in self._grok_list:
                pattern_matches[grok.pattern] = 0
            self._match_cnt_initialized = True

        for grok in self._grok_list:
            matches = grok.match(text)
            if matches:
                if pattern_matches is not None:
                    pattern_matches[grok.pattern] += 1
                dotted_matches = {}
                for key, value in matches.items():
                    dotted_matches[self.grok_delimiter_pattern.sub(".", key)] = value
                return dotted_matches
        return {}


class NormalizerRule(Rule):
    """Check if documents match a filter."""

    additional_grok_patterns = None
    extract_field_pattern = re.compile(r"%{(\w+):([\w\[\]]+)(?::\w+)?}")
    sub_fields_pattern = re.compile(r"(\[(\w+)\])")

    # pylint: disable=super-init-not-called
    # TODO: this is not refactored, because this processor should be dissected
    def __init__(
        self, filter_rule: FilterExpression, normalizations: dict, description: str = None
    ):
        self.__class__.__hash__ = Rule.__hash__
        self.filter_str = str(filter_rule)
        self._filter = filter_rule
        self._special_fields = None
        self.file_name = None
        self._tests = []
        self.metrics = self.RuleMetrics(labels={"type": "rule"})
        self._substitutions = {}
        self._grok = {}
        self._timestamps = {}
        self.description = description

        self._parse_normalizations(normalizations)

    # pylint: enable=super-init-not-called

    def _parse_normalizations(self, normalizations):
        for source_field, normalization in normalizations.items():
            if isinstance(normalization, dict) and normalization.get("grok"):
                self._extract_grok_pattern(normalization, source_field)
            elif isinstance(normalization, dict) and normalization.get("timestamp"):
                self._timestamps.update({source_field: normalization})
            else:
                self._substitutions.update({source_field: normalization})

    def _extract_grok_pattern(self, normalization, source_field):
        """Checks the rule file for grok pattern, reformats them and adds them to self._grok"""
        if isinstance(normalization["grok"], str):
            normalization["grok"] = [normalization["grok"]]
        for idx, grok in enumerate(normalization["grok"]):
            patterns = self.extract_field_pattern.findall(grok)
            self._reformat_grok_pattern(idx, normalization, patterns)
            failure_target_field = normalization.get("failure_target_field")
            self._grok.update(
                {
                    source_field: GrokWrapper(
                        patterns=normalization["grok"],
                        custom_patterns_dir=NormalizerRule.additional_grok_patterns,
                        failure_target_field=failure_target_field,
                    )
                }
            )

    def _reformat_grok_pattern(self, idx, normalization, patterns):
        """
        Changes the grok pattern format by removing the square brackets and introducing
        the GROK_DELIMITER.
        """
        for pattern in patterns:
            if len(pattern) >= 2:
                sub_fields = re.findall(self.sub_fields_pattern, pattern[1])
                if sub_fields:
                    mutable_pattern = list(pattern)
                    mutable_pattern[1] = GROK_DELIMITER.join(
                        (sub_field[1] for sub_field in sub_fields)
                    )
                    to_replace = re.escape(r"%{" + r":".join(pattern))
                    transformed_fields_names = "%{" + ":".join(mutable_pattern)
                    normalization["grok"][idx] = re.sub(
                        to_replace, transformed_fields_names, normalization["grok"][idx]
                    )

    def __eq__(self, other: "NormalizerRule") -> bool:
        return all(
            [
                other.filter == self._filter,
                self._substitutions == other.substitutions,
                self._grok == other.grok,
                self._timestamps == other.timestamps,
            ]
        )

    # pylint: disable=C0111
    @property
    def substitutions(self) -> dict:
        return self._substitutions

    @property
    def grok(self) -> dict:
        return self._grok

    @property
    def timestamps(self) -> dict:
        return self._timestamps

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "NormalizerRule":
        NormalizerRule._check_rule_validity(rule, "normalize")
        NormalizerRule._check_if_normalization_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        description = rule.get("description")
        return NormalizerRule(filter_expression, rule["normalize"], description)

    @staticmethod
    def _check_if_normalization_valid(rule: dict):
        for value in rule["normalize"].values():
            if isinstance(value, list):
                if len(value) != 3:
                    raise InvalidNormalizationDefinition(value)
            if isinstance(value, dict):
                NormalizerRule._validate_allowed_keys(value)
                if "grok" in value.keys():
                    NormalizerRule._validate_grok(value)
                if "timestamp" in value.keys():
                    NormalizerRule._validate_timestamp(value)

    @staticmethod
    def _validate_allowed_keys(value):
        allowed_keys = ["grok", "timestamp", "failure_target_field"]
        if any(key for key in value.keys() if key not in allowed_keys):
            raise InvalidNormalizationDefinition(value)

    @staticmethod
    def _validate_grok(value):
        grok = value["grok"]
        if not grok:
            raise InvalidNormalizationDefinition(value)
        if isinstance(grok, list):
            if any(not isinstance(pattern, str) for pattern in grok):
                raise InvalidNormalizationDefinition(value)
        try:
            GrokWrapper(grok, custom_patterns_dir=NormalizerRule.additional_grok_patterns)
        except Exception as error:
            raise InvalidGrokDefinition(grok) from error

    @staticmethod
    def _validate_timestamp(value):
        timestamp = value.get("timestamp")
        if not timestamp:
            raise InvalidNormalizationDefinition(value)
        if not isinstance(timestamp.get("destination"), str):
            raise InvalidTimestampDefinition(timestamp)
        if not isinstance(timestamp.get("source_formats"), list):
            raise InvalidTimestampDefinition(timestamp)
        if not isinstance(timestamp.get("source_timezone"), str):
            raise InvalidTimestampDefinition(timestamp)
        if not isinstance(timestamp.get("destination_timezone"), str):
            raise InvalidTimestampDefinition(timestamp)
