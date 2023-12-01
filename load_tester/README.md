# Load Tester
The load-tester can send a configurable amount of documents to Kafka.
The documents that are being send can be obtained either from Kafka or from a file with JSON lines.

It can be configured how many documents should be retrieved from Kafka (if Kafka is used as source) and how many documents will be sent.
Documents obtained from Kafka won't be written down to disk.

The documents will be sent repeatedly until the desired amount has been sent.
The `tags` field and the `_index` field of each document will be set to `load-tester`. 
Furthermore, a field `load-tester-unique` with a unique value will be added to each document every time a document is sent.
This is done to prevent that repeatedly sent documents are identical.


## Requirements
Python3 must be installed.

## Installation
The requirements must be installed: `pip -r requirements.txt`

## Configuration
The script is configured via a YAML file.
It must have the following format:

```yaml
logging_level: LOG_LEVEL  # Default: "INFO"
source_count: INTERGER  # Number of documents to obtain form Kafka
count: INTERGER  # Number of documents to send
process_count: INTERGER  # Number of processes (default: 1)
profile: BOOL  # Shows profiling data (default: false)
target_send_per_sec: INTERGER  # Desired number of documents to send per second with each process. Setting it to 0 sends as much as possible (default: 0).

kafka:
  bootstrap_servers:  # List of bootstrap servers
    - URL:PORT  # i.e. "127.0.0.1:9092" 
  consumer:  # Kafka consumer
    topic: STRING  # Topic to obtain documents from
    group_id: STRING  # Should be different from the group_id of the Logprep Consumer, otherwise the offset in Logprep will be changed!
    timeout: FLOAT  # Timeout for retrieving documents (default: 1.0) 
  producer:  # Kafka producer
    acks: STRING/INTERGER # Determines if sending should be acknowledged (default: 0)
    compression_type: STRING  # Compression type (default: "none")
    topic: STRING  # Topic to send documents to
    queue_buffering_max_messages: INTEGER # Batch for sending documents (default: 10000)
    linger_ms: INTEGER # Time to wait before a batch is sent if the max wasn't reached before (default: 5000)
    flush_timeout: FLOAT # Timeout to flush the producer (default 30.0)
  ssl:  # SSL authentication (Optional)
    ca_location: STRING
    certificate_location: STRING
    key:
      location: STRING
      password: STRING # Optional
```
Unused parameters must be removed or commented.

## Usage
The script is executed with the file `run_load_tester.py` using Python.
Documents will be read from Kafka per default. Giving the argument `--file PATH` uses a file instead.

```
usage: run_load_tester.py [-h] [-f FILE] config

positional arguments:
  config                Path to configuration file

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  Path to file with documents
```
