# Brainstorm
- Environment config bleibt, wildcard mechanismus in der config.json
- Sollen HttpGetter gehalten werden oder soll protocol gestrippt werden / überhaupt nicht mehr gestrippt werden
- Cleanup callback wie genau?
- Deallokierung von Prozessor führt zu was?
- signal_called umbennenen zu ?

# Implement
- Template benutzen anstatt regex (get_identifiers)
- der erste match in config.json gewinnt
- glob / prefix und kein regex als target key
- besser das protocol strippen als http getter halten
  - protocol soll teil des targets werden wenn möglich
- hinzufügen von add_cleanup_callback um compare_sets nach timeout / keepalive zu löschen
- DataSharedPerTaget tagging von Prozessor, um nur Prozessor gebundene callbacks zu deregistrieren
