=============
Rule Language
=============

Basic Functionality
===================

How processors process log messages is defined via configurable rules.
Each rule contains a filter that is used to select log messages.
Other parameters within the rules define how certain log messages should be transformed.
Those parameters depend on the processor for which they were created.

Rule Files
==========

Rules are defined as YAML objects or JSON objects.
Rules can be distributed over different files or multiple rules can reside within one file.
Each file contains multiple YAML documents or a JSON array of JSON objects.
The YAML format is preferred, since it is a superset of JSON and has better readability.

Depending on the filter, a rule can trigger for different types of messages or just for specific log messages.
In general, specific rules are being applied first.
It depends on the directory where the rule is located if it is considered specific or generic.

Further details can be found in the section for processors.

..  code-block:: yaml
    :linenos:
    :caption: Example structure of a YAML file with a rule for the labeler processor

    filter: 'command: execute'  # A comment
    label:
      action:
      - execute
    description: '...'

..  code-block:: yaml
    :linenos:
    :caption: Example structure of a YAML file containing multiple rules for the labeler processor

    filter: 'command: "execute something"'
    label:
      action:
      - execute
    description: '...'
    ---
    filter: 'command: "terminate something"'
    label:
      action:
      - terminate
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Example structure of a JSON file with a rule for the labeler processor

    [{
      "filter": "command: execute",
      "label": {
        "action": ["execute"]
      },
      "description": "..."
    }]

..  code-block:: json
    :linenos:
    :caption: Example structure of a JSON file containing multiple rules for the labeler processor

    [{
      "filter": "command: \"execute something\"",
      "label": {
        "action": ["execute"]
      },
      "description": "..."
    },
    {
      "filter": "command: \"terminate something\"",
      "label": {
        "action": ["terminate"]
      },
      "description": "..."
    }]

Filter
======

The filters are based on the Lucene query language, but contain some additional enhancements.
It is possible to filter for keys and values in log messages.
**Dot notation** is used to access subfields in log messages.
A filter for :code:`{'field': {'subfield': 'value'}}` can be specified by :code:`field.subfield': 'value`.

If a key without a value is given it is filtered for the existence of the key.
The existence of a specific field can therefore be checked by a key without a value.
The filter :code:`filter: field.subfield` would match for every value :code:`subfield` in :code:`{'field': {'subfield': 'value'}}`.
The special key :code:`*` can be used to always match on any input.
Thus, the filter :code:`filter: *` would match any input document.

The filter in the following example would match fields :code:`ip_address` with the value :code:`192.168.0.1`.
Meaning all following transformations done by this rule would be applied only on log messages that match this criterion.
This example is not complete, since rules are specific to processors and require additional options.


..  code-block:: json
    :linenos:
    :caption: Example

    { "filter": "ip_address: 192.168.0.1" }

It is possible to use filters with field names that contain white spaces or use special symbols of the Lucene syntax.
However, this has to be escaped.
The filter :code:`filter: 'field.a subfield(test): value'` must be escaped as :code:`filter: 'field.a\ subfield\(test\): value'`.
Other references to this field do not require such escaping.
This is *only* necessary for the filter.
It is necessary to escape twice if the file is in the JSON format - once for the filter itself and once for JSON.

Operators
---------

A subset of Lucene query operators is supported:

- **NOT**: Condition is not true.
- **AND**: Connects two conditions. Both conditions must be true.
- **OR**: Connects two conditions. At least one them must be true.

In the following example log messages are filtered for which :code:`event_id: 1` is true and :code:`ip_address: 192.168.0.1` is false.
This example is not complete, since rules are specific to processors and require additional options.


..  code-block:: json
    :linenos:
    :caption: Example

    { "filter": "event_id: 1 AND NOT ip_address: 192.168.0.1" }

RegEx-Filter
------------

It is possible use regex expressions to match values.
For this, the field with the regex pattern must be added to the optional field :code:`regex_fields` in the rule definition.

In the following example the field :code:`ip_address` is defined as regex field.
It would be filtered for log messages in which the value :code:`ip_address` starts with :code:`192.168.0.`.
This example is not complete, since rules are specific to processors and require additional options.


..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'ip_address: "192\.168\.0\..*"'
    regex_fields:
    - ip_address

Labeler
=======

The labeler requires the additional field :code:`label`.
The keys under :code:`label` define the categories under which a label should be added.
The values are a list of labels that should be added under a category.

In the following example, the label :code:`execute` will be added to the labels of the category :code:`action`:

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'command: "executing something"'
    label:
      action:
      - execute
    description: '...'

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
This can be combined with the normalizations that have been already introduced or it can be used instead of them.
By combining both types of normalization it is possible to perform transformations on results of Grok that can not be achieved by Grok alone.
All Grok normalizations are always performed before other normalizations.
An example for this is the creation of nested fields.

The following example would normalize :code:`event_data.ip_and_port: "Linus has the address 1.2.3.4 1234", event_data.address_text: "This is an address: 1.2.3.4:1234"` to
:code:`address.ip: "1.2.3.4"`, :code:`address.port: 1234`, :code:`name: Linus` and :code:`address.combined: 1.2.3.4 and 1234`.

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

It is furthermore possible to use more than one Grok pattern for a field by specifying them in a list.
The patterns will be sequentially checked until one of them matches.

The following example would normalize :code:`some_field_with_an_ip: "1.2.3.4 1234"` to :code:`ip: "1.2.3.4"`, :code:`port: 1234`, skipping the first Grok pattern.
:code:`some_field_with_an_ip: "1.2.3.4 1234 foo"` would be however normalized to :code:`ip_foo: "1.2.3.4"`, :code:`port_foo: 1234`.

..  code-block:: yaml
    :linenos:
    :caption: Example - Grok normalization with multiple patterns

      filter: 'some_field_with_an_ip'
      normalize:
      some_field_with_an_ip:
        grok:
        - '%{IP:ip_foo} %{NUMBER:port_foo:int} foo'
        - '%{IP:ip} %{NUMBER:port:int}'

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

Generic Adder
=============

The generic adder requires the additional field :code:`generic_adder`.
The field :code:`generic_adder.add` can be defined.
It contains a dictionary of field names and values that should be added.
If dot notation is being used, then all fields on the path are being automatically created.

In the following example, the field :code:`some.added.field` with the value :code:`some added value` is being added.


..  code-block:: yaml
    :linenos:
    :caption: Example with add

    filter: add_generic_test
    generic_adder:
      add:
        some.added.field: some added value
    description: '...'

Alternatively, the additional field :code:`generic_adder.add_from_file` can be added.
It contains the path to a file with a YML file that contains a dictionary of field names and values that should be added to the document.
Instead of a path, a list of paths can be used to add multiple files.
All of those files must exist.
If a list is used, it is possible to tell the generic adder to only use the first existing file by setting :code:`generic_adder.only_first_existing_file: true`.
In that case, only one file must exist.

In the following example a dictionary with field names and values is loaded from the file at :code:`PATH_TO_FILE_WITH_LIST`.
This dictionary is used like the one that can be defined via :code:`generic_adder.add`.

..  code-block:: yaml
    :linenos:
    :caption: Example with add_from_file

    filter: 'add_generic_test'
    generic_adder:
      add_from_file: PATH_TO_FILE_WITH_LIST
    description: '...'

In the following example two files are being used.

..  code-block:: yaml
    :linenos:
    :caption: Example with multiple files

    filter: 'add_generic_test'
    generic_adder:
      add_from_file:
        - PATH_TO_FILE_WITH_LIST
        - ANOTHER_PATH_TO_FILE_WITH_LIST
    description: '...'

In the following example two files are being used, but only the first existing file is being loaded.

..  code-block:: yaml
    :linenos:
    :caption: Example with multiple files and one loaded file

    filter: 'add_generic_test'
    generic_adder:
      only_first_existing_file: true
      add_from_file:
        - PATH_TO_FILE_THAT_DOES_NOT_EXIST
        - PATH_TO_FILE_WITH_LIST
    description: '...'

It is also possible to use a table from a MySQL database to add fields to an event.
If a specified field in the table matches a condition, the remaining fields, except for the ID field,
will be added to the event.
The names of the new fields correspond to the column names in the MySQL table.
This is mutually exclusive with the addition from a list.

It can be defined via :code:`generic_adder.sql_table`.
There :code:`generic_adder.sql_table.event_source_field` defines a field in the event that is being compared with values in the column of the MySQL table defined in the processor config.
However, only a part of :code:`event_source_field` will be compared.
Which part this is can be configured via :code:`generic_adder.sql_table.pattern`.
This is a regex pattern with a capture group.
The value in the capture group is being extracted and used for the comparison.
:code:`generic_adder.sql_table.destination_field_prefix` can be used to prefix all added fields with a dotted path, creating a nested dictionary.

In the following example the value of the field :code:`source` is being parsed with :code:`pattern: ([a-zA-Z0-9]+)_\S+`.
It extracts the first alphanumerical string delimited by :code:`_`.
I.e., :code:`Test0_foobarbaz` would extract :code:`test0`, which would be used for the comparison in the MySQL table.
Since :code:`destination_field_prefix: nested.dict` is set, a newly added field :code:`FOO_NEW` would be placed under :code:`nested.dict.FOO_NEW`.

..  code-block:: yaml
    :linenos:
    :caption: Example with a MySQL Table

    filter: '*'
    generic_adder:
      sql_table:
        event_source_field: source
        pattern: '([a-zA-Z0-9]+)_\S+'
        destination_field_prefix: nested.dict
    description: '...'

Selective Extractor
===================

The selective extractor requires the additional field :code:`selective_extractor`.
The field :code:`selective_extractor.extract` has to be defined.
It contains a dictionary of field names that should be extracted and a target topic to which they should be send to.
If dot notation is being used, then all fields on the path are being automatically created.

In the following example, the field :code:`field.extract` with the value :code:`extracted value` is being extracted
and send to the topic :code:`topcic_to_send_to`.

..  code-block:: yaml
    :linenos:
    :caption: Example rule with extract from field list

    filter: extract_test
    selective_extractor:
      extract:
        extracted_field_list: ["field.extract", "field2", "field3"]
        target_topic: topic_to_send_to
    description: '...'


..  code-block:: json
    :caption: Example event

    {
      "extract_test": {
        "field": {
          "extract": "extracted value"
        }
      }
    }

..  code-block:: json
    :caption: Extracted event from Example

    {
      "extract": "extracted value"
    }



Alternatively, the additional field :code:`selective_extractor.extract.extract_from_file` can be added.
It contains the path to a text file with a list of fields per line to be extracted.

..  code-block:: yaml
    :linenos:
    :caption: Example rule with extract from file

    filter: extract_test
    selective_extractor:
      extract:
        extract_from_file: /path/to/file
        target_topic: topic_to_send_to
    description: '...'


..  code-block:: text
    :caption: Example of file with field list

    field1
    field2
    field3

The file has to exist.

It is possible to mix both extraction sources. They will be merged to one list without duplicates.

..  code-block:: yaml
    :linenos:
    :caption: Example rule with extract from file

    filter: extract_test
    selective_extractor:
      extract:
        extract_from_file: /path/to/file
        extracted_field_list: ["field1", "field2", "field4"]
        target_topic: topic_to_send_to
    description: '...'


..  code-block:: text
    :caption: Example of file with field list

    field1
    field2
    field3

Datetime Extractor
==================

The datetime extractor requires the additional field :code:`datetime_extractor`.
The additional fields :code:`datetime_extractor.datetime_field` and :code:`datetime_extractor.destination_field` must be defined.
The first one contains the name of the field from which the timestamp should be taken and the last one contains the name of the field under which a split timestamp should be written.

In the following example the timestamp will be extracted from :code:`@timestamp` and written to :code:`split_@timestamp`.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: '@timestamp'
    datetime_extractor:
      datetime_field: '@timestamp'
      destination_field: 'split_@timestamp'
    description: '...'

Domain Resolver
===============

The domain resolver requires the additional field :code:`domain_resolver`.
The additional field :code:`domain_resolver.source_url_or_domain` must be defined.
It contains the field from which an URL should be parsed and then written to :code:`resolved_ip`.
The URL can be located in continuous text insofar the URL is valid.

Optionally, the output field can be configured (overriding the default :code:`resolved_ip`) using the parameter :code:`output_field`.
This can be a dotted subfield.

In the following example the URL from the field :code:`url` will be extracted and written to :code:`resolved_ip`.

..  code-block:: yaml
    :linenos:
    :caption: Example

      filter: url
      domain_resolver:
        source_url_or_domain: url
      description: '...'

Domain Label Extractor
======================

The domain label extractor requires the additional field :code:`domain_label_extractor`.
The mandatory keys under :code:`domain_label_extractor` are :code:`target_field` and :code:`output_field`. Former
is used to identify the field which contains the domain. And the latter is used to define the parent field where the
results should be written to. Both fields can be dotted subfields. The sub fields of the parent output field of the
result are: :code:`registered_domain`, :code:`top_level_domain` and :code:`subdomain`.

In the following example the domain :code:`www.sub.domain.de` will be split into it's subdomain :code:`www.sub`, it's
registered domain :code:`domain` and lastly it's TLD :code:`de`:

..  code-block:: yaml
    :linenos:
    :caption: Example Rule to extract the labels / parts of a domain.

    filter: 'url'
    domain_label_extractor:
      target_field: 'url.domain'
      output_field: 'url'
    description: '...'

The example rule applied to the input event

..  code-block:: json
    :caption: Input Event

    {
        "url": {
            "domain": "www.sub.domain.de"
        }
    }

will result in the following output

..  code-block:: json
    :caption: Output Event

    {
        "url": {
            "domain": "www.sub.domain.de",
            "registered_domain": "domain.de",
            "top_level_domain": "de",
            "subdomain": "www.sub"
        }
    }


List Comparison Enricher
========================

The list comparison enricher requires the additional field :code:`list_comparison`.
The mandatory keys under :code:`list_comparison` are :code:`check_field` and :code:`output_field`. Former
is used to identify the field which is to be checked against the provided lists. And the latter is used to define
the parent field where the results should be written to. Both fields can be dotted subfields.

Additionally, a list or array of lists can be provided underneath the required field :code:`list_file_paths`.

In the following example, the field :code:`user_agent` will be checked against the provided list
(:code:`priviliged_users.txt`).
Assuming that the value :code:`non_privileged_user` will match the provided list, the result of the list comparison
(:code:`in_list`) will be added to the output field :code:`List_comparison.example`.

..  code-block:: yaml
    :linenos:
    :caption: Example Rule to compare a single field against a provided list.

    filter: 'user_agent'
    list_comparison:
      check_field: 'user_agent'
      output_field: 'List_comparison.example'
    list_file_paths:
        -   lists/privileged_users.txt
    description: '...'

Geoip Enricher
==============

The geoip enricher requires the additional field :code:`geoip`.
The default output_field can be overridden using the optional parameter :code:`output_field`. This can be a dotted
subfield. The additional field :code:`geoip.source_ip` must be given. It contains the IP for which the geoip data
should be added.

In the following example the IP in :code:`client.ip` will be enriched with geoip data.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: client.ip
    geoip:
      source_ip: client.ip
    description: '...'

Template Replacer
=================

The template replacer requires the additional field :code:`template_replacer`.
No additional configuration parameters are required for the rules.
The module is completely configured over the pipeline configuration.

In the following example the target field specified in the processor configuration is replaced for all log messages that have :code:`winlog.provider_name` and :code:`winlog.event_id` if it is defined in the template file.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: winlog.provider_name AND winlog.event_id
    template_replacer: {}
    description: ''

Generic Resolver
================

The generic adder requires the additional field :code:`generic_resolver`.
It works similarly to the hyperscan resolver, which utilizes hyperscan to process resolve lists.
Configurable fields are being checked by regex patterns and a configurable value will be added if a pattern matches.
The parameters within :code:`generic_resolver` must be of the form
:code:`field_mapping: {SOURCE_FIELD: DESTINATION_FIELD}, resolve_list: {REGEX_PATTERN_0: ADDED_VALUE_0, ..., REGEX_PATTERN_N: ADDED_VALUE_N}`.
SOURCE_FIELD will be checked by the regex patterns REGEX_PATTERN_[0-N] and a new field DESTINATION_FIELD with the value ADDED_VALUE_[0-N] will be added if there is a match.
Adding the option :code:`"append_to_list": True` makes the generic resolver write resolved values into a list so that multiple different values can be written into the same field.

In the following example :code:`to_resolve` will be checked by the regex pattern :code:`.*Hello.*`.
:code:`"resolved": "Greeting"` will be added to the event if the pattern matches the value in :code:`to_resolve`.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: to_resolve
    generic_resolver:
      field_mapping:
        to_resolve: resolved
      resolve_list:
        .*Hello.*: Greeting

Alternatively, a YML file with a resolve list and a regex pattern can be used to resolve values.
For this, a field :code:`resolve_from_file` with the subfields :code:`path` and :code:`pattern` must be added.
The resolve list in the file at :code:`path` is then used in conjunction with the regex pattern in :code:`pattern`.
:code:`pattern` must be a regex pattern with a capture group that is named :code:`mapping`.
The resolver will check for the pattern and get value captured by the :code:`mapping` group.
This captured value is then used in the list from the file.

In the following example :code:`to_resolve` will be checked by the regex pattern :code:`\d*(?P<mapping>[a-z]+)\d*` and the list in :code:`path/to/resolve_mapping.yml` will be used to add new fields.
:code:`"resolved": "resolved foo"` will be added to the event if the value in :code:`to_resolve` begins with number, ends with numbers and contains foo.
Furthermore, :code:`"resolved": "resolved bar"` will be added to the event if the value in :code:`to_resolve` begins with number, ends with numbers and contains bar.

..  code-block:: yaml
    :linenos:
    :caption: Example resolving with list from file

    filter: to_resolve
    generic_resolver:
      field_mapping:
        to_resolve: resolved
      resolve_from_file:
        path: path/to/resolve_mapping.yml
        pattern: \d*(?P<mapping>[a-z]+)\d*

..  code-block:: yaml
    :linenos:
    :caption: Example file with resolve list

    foo: resolved foo
    bar: resolved bar

Hyperscan Resolver
==================

The hyperscan resolver requires the additional field :code:`hyperscan_resolver`.
It works similarly to the generic resolver, but utilized hyperscan to process resolve lists.
Configurable fields are being checked by regex patterns and a configurable value will be added if a pattern matches.
The parameters within :code:`hyperscan_resolver` must be of the form
:code:`field_mapping: {SOURCE_FIELD: DESTINATION_FIELD}, resolve_list: {REGEX_PATTERN_0: ADDED_VALUE_0, ..., REGEX_PATTERN_N: ADDED_VALUE_N}`.
SOURCE_FIELD will be checked by the regex patterns REGEX_PATTERN_[0-N] and a new field DESTINATION_FIELD with the value ADDED_VALUE_[0-N] will be added if there is a match.
Adding the option :code:`"append_to_list": True` makes the hyperscan resolver write resolved values into a list so that multiple different values can be written into the same field.

In the following example :code:`to_resolve` will be checked by the regex pattern :code:`.*Hello.*`.
:code:`"resolved": "Greeting"` will be added to the event if the pattern matches the value in :code:`to_resolve`.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: to_resolve
    hyperscan_resolver:
      field_mapping:
        to_resolve: resolved
      resolve_list:
        .*Hello.*: Greeting

Alternatively, a YML file with a resolve list and an optional regex pattern can be used to resolve values.
For this, either a field :code:`resolve_from_file` with a path to a resolve list file must be added
or dictionary field :code:`resolve_from_file` with the subfields :code:`path` and :code:`pattern`.
Using the :code:`pattern` option allows to define one regex pattern that can be used on all entries within a
resolve list instead of having to write a regex pattern for each entry in the list.
The resolve list in the file at :code:`path` is then used in conjunction with the regex pattern in :code:`pattern`.
:code:`pattern` must be a regex pattern with a capture group that is named :code:`mapping`.
The entries in the resolve list are then transformed by the pattern.
At first, the pattern is matched with each list entry in the resolve list.
If the capture group :code:`mapping` matches, then the capture group in the pattern is replaced with the matching result.
This replaced pattern is then used instead of the original mapping within the resolve list file.
This effectively wraps the list entries with the regex pattern.

In the following example :code:`to_resolve` will be checked by the list in :code:`path/to/resolve_mapping.yml`.
:code:`"resolved": "resolved foo"` will be added to the event if the value in :code:`to_resolve` matches a pattern in the file.
Furthermore, :code:`"resolved": "resolved bar"` will be added to the event if the value in :code:`to_resolve` begins with number, ends with numbers and contains bar.

..  code-block:: yaml
    :linenos:
    :caption: Example resolving with list from file

    filter: to_resolve
    hyperscan_resolver:
      field_mapping:
        to_resolve: resolved
      resolve_from_file: path/to/resolve_mapping.yml

..  code-block:: yaml
    :linenos:
    :caption: Example file with resolve list

    \d*foo\d*: resolved foo
    \d*bar\d*: resolved bar

In the following example :code:`to_resolve` will be checked with the regex pattern :code:`\d*(?P<mapping>[a-z]+)\d*` and the list in :code:`path/to/resolve_mapping.yml` will be used to add new fields.
:code:`"resolved": "resolved foo"` will be added to the event if the value in :code:`to_resolve` begins with number, ends with numbers and contains foo.
Furthermore, :code:`"resolved": "resolved bar"` will be added to the event if the value in :code:`to_resolve` begins with number, ends with numbers and contains bar.

..  code-block:: yaml
    :linenos:
    :caption: Example resolving with list from file

    filter: to_resolve
    hyperscan_resolver:
      field_mapping:
        to_resolve: resolved
      resolve_from_file:
        path: path/to/resolve_mapping.yml
        pattern: \d*(?P<mapping>[a-z]+)\d*

..  code-block:: yaml
    :linenos:
    :caption: Example file with resolve list

    foo: resolved foo
    bar: resolved bar

The hyperscan resolver uses the `Python Hyperscan library <https://python-hyperscan.readthedocs.io/en/latest/>`_ to check regex patterns.
By default, the compiled Hyperscan databases will be stored persistently in the directory specified in the :code:`pipeline.yml`.
The field :code:`store_db_persistent` can be used to configure if a database compiled from a rule's :code:`resolve_list` should be stored persistently.

PreDetector
===========

The predetector requires the additional field :code:`pre_detector`.
Below this, the following subfields must be provided, which are based on the Sigma format:

  * :code:`id`: An ID for the triggered rule
  * :code:`title`: A description for the triggered rule
  * :code:`severity`: Rating how dangerous an Event is (i.e. `critical`)
  * :code:`mitre`: A list of MITRE ATT&CK tags
  * :code:`case_condition`: The type of the triggered rule (mostly `directly`)

Those fields and a `pre_detector_id` are written into an own Kafka topic.
The `pre_detector_id` will be furthermore added to the triggering event so that an event can be linked with its detection.

The following example shows a complete rule:

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'some_field: "very malicious!"'
    pre_detector:
      case_condition: directly
      id: RULE_ONE_ID
      mitre:
      - attack.something1
      - attack.something2
      severity: critical
      title: Rule one
    description: Some malicous event.

Additionally the optional field :code:`ip_fields` can be specified.
It allows to specify a list of fields that can be compared to a list of IPs, which can be configured in the pipeline for the predetector.
If this field was specified, then the rule will *only* trigger in case one of the IPs from the list is also available in the specified fields.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'some_field: something AND some_ip_field'
    pre_detector:
      id: RULE_ONE_ID
      title: Rule one
      severity: critical
      mitre:
      - some_tag
      case_condition: directly
    description: Some malicous event.
    ip_fields:
    - some_ip_field

Pseudonymizer
=============

The pseudonymizer requires the additional field :code:`pseudonymize`.
It contains key value pairs that define what will be pseudonymized.

They key represents the field that will be pseudonymized and the value contains a regex keyword.
The regex keyword defines which parts of the value are being pseudonymized.
Only the regex matches are being pseudonymized that are also in a capture group.
An arbitrary amount of capture groups can be used.
The definitions of regex keywords are located in a separate file.

In the following the field :code:`event_data.param1` is being completely pseudonymized.
This is achieved by using the predefined keyword :code:`RE_WHOLE_FIELD`, which will be resolved to a regex expression.
:code:`RE_WHOLE_FIELD` resolves to :code:`(.*)` which puts the whole match in a capture group and therefore pseudonymizes it completely.

..  code-block:: yaml
    :linenos:
    :caption: Example - Rule

    filter: 'event_id: 1 AND source_name: "Test"'
    pseudonymize:
      event_data.param1: RE_WHOLE_FIELD
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Example - Regex mapping file

    {
      "RE_WHOLE_FIELD": "(.*)",
      "RE_DOMAIN_BACKSLASH_USERNAME": "\\w+\\\\(.*)",
      "RE_IP4_COLON_PORT": "([\\d.]+):\\d+"
    }

Clusterer
=========

Rules of the clusterer are evaluated in alphanumerical order.
Some rules do only make sense if they are performed in a sequence with other rules.
The clusterer matches multiple rules at once and applies them all before creating a clustering signature.
Therefore, it is recommended to prefix rules with numbers, i.e. `00_01_*`.
Here the first two digits represent a type of rules that make sense together and the second digits represent the order of rules of the same type.

The clusterer requires the additional field :code:`clusterer`.
Which field is used for clustering is defined in :code:`clusterer.target`.
This should be usually the field :code:`message`.
A subset of terms from this field can be extracted into the clustering-signature field defined in the clusterer configuration.
The field :code:`clusterer.pattern` contains a regex pattern that will be matched on :code:`clusterer.target`.
Anything within a capture group in :code:`clusterer.pattern` will be substituted with values defined in :code:`clusterer.repl`.
The clusterer will only extract terms into a signature that are surrounded by the tags `<+></+>`.
One could first use rules to remove common terms, other rules to perform stemming and finally rules to wrap terms in `<+></+>` to create a signature.

For example:
  * Setting :code:`clusterer.repl: ''` would remove anything within a capture group.
  * Setting :code:`clusterer.repl: 'FOO'` would replace anything within a capture group with `FOO`.
  * Setting :code:`clusterer.repl: '<+>\1</+>'` would surround anything within a capture group with `<+></+>`.

Since clusterer rules must be used in a sequence, it makes no sense to perform regular auto tests on them.
Thus, every rule can have a field :code:`tests` containing signature calculation tests.
It can contain one test or a list of tests.
Each tests consists of the fields :code:`tests.raw` and :code:`tests.result`.
:code:`tests.raw` is the input and would be usually the message.
:code:`tests.result` is the expected result.

..  code-block:: yaml
    :linenos:
    :caption: Example - One Test

    filter: ...
    clusterer: ...
    tests:
      raw:    'Some message'
      result: 'Some changed message'

..  code-block:: yaml
    :linenos:
    :caption: Example - Multiple Test

    filter: ...
    clusterer: ...
    tests:
      - raw:    'Some message'
        result: 'Some changed message'
      - raw:    'Another message'
        result: 'Another changed message'

In the following rule example the word `byte` is stemmed.

..  code-block:: yaml
    :linenos:
    :caption: Example - Stemming Rule

    filter: message
    clusterer:
      target: message
      pattern: '(bytes|Bytes|Byte)'
      repl: 'byte'
    description: '...'
    tests:
      raw:    'Byte is a Bytes is a bytes is a byte'
      result: 'byte is a byte is a byte is a byte'

In the following rule example the word `baz` is removed.

..  code-block:: yaml
    :linenos:
    :caption: Example - Removal Rule

    filter: message
    clusterer:
      target: message
      pattern: 'foo (bar) baz'
      repl: ''
    description: '...'
    tests:
      raw:    'foo bar baz'
      result: 'foo  baz'

In the following rule example the word `baz` is surrounded by extraction tags.

..  code-block:: yaml
    :linenos:
    :caption: Example - Extraction Rule

    filter: message
    clusterer:
      target: message
      pattern: 'foo (bar) baz'
      repl: '<+>\1</+>'
    description: '...'
    tests:
      raw:    'foo bar baz'
      result: 'foo <+>bar</+> baz'

Dropper
=======

Which fields are removed is defined in the additional field :code:`drop`.
It contains a list of fields in dot notation.
For nested fields all subfields are also removed if they are empty.
If only the specified subfield should be removed, then this can be achieved by setting the option :code:`drop_full: false`.

In the following example the field :code:`keep_me.drop_me` is deleted while the fields :code:`keep_me` and :code:`keep_me.keep_me_too` are kept.

..  code-block:: yaml
    :linenos:
    :caption: Example - Rule

    filter: keep_me.drop_me
    drop:
    - keep_me.drop_me

..  code-block:: json
    :linenos:
    :caption: Example - Input document

    [{
        "keep_me": {
            "drop_me": "something",
            "keep_me_too": "something"
        }
    }]

..  code-block:: json
    :linenos:
    :caption: Example - Expected output after application of the rule

    [{
        "keep_me": {
            "keep_me_too": "something"
        }
    }]
