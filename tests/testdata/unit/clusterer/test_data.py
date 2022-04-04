import collections
from collections import defaultdict
from types import SimpleNamespace
import re

from logprep.processor.clusterer.signature_calculation.rules.rule_template import SignatureRule
from logprep.processor.clusterer.signature_calculation.signature_phase import LogRecord


class LogRecordTest(LogRecord):
    sig_token_pos_list = []


class DatasetSignatureProcessing:
    test_record_1 = LogRecordTest()

    test_record_1.raw_text = (
        "Dec  9 12:58:10 bastion sendmail[16194]: gB9HwAC16191: to=root, ctladdr=root (0/0), "
        "delay=00:00:00, xdelay=00:00:00, mailer=local, pri=30251, dsn=2.0.0, stat=Sent, "
        "did not issue MAIL/EXPN/VRFY/ETRN during, xinetd Version 2.3.10, [pulseaudio] pid.c: "
        "Daemon already running. DHCPREQUEST of 11.22.233.244 on eno1 to 11.22.33.44 port 67 "
        "(xid=0x26da5e58), Failed password for root from 111.222.233.244 port 40757 ssh2, "
        "authentication failure; logname= uid=0 euid=0 tty=NODEVssh ruser= "
        "rhost=wpc0824.amenworld.com  user=root, to=<root@combo.honeypotbox.com>, "
        "ctladdr=<root@combo.honeypotbox.com> (0/0), delay=00:00:01, xdelay=00:00:01, "
        "mailer=local, pri=69940, dsn=2.0.0, [Classification: Potential Corporate "
        "Privacy Violation] [Priority: 1]: {TCP} 11.22.33.44:1060 -> 111.222.23.2:1234, "
        "Closed dest port used: local dest, syn: 0.9550 {TCP} 111.222.23.26:2222 -> "
        "11.22.33.44:8000, IN=br0 PHYSIN=eth0 OUT=br0 PHYSOUT=eth1 SRC=121.123.111.50 "
        "DST=11.22.33.44 LEN=404 TOS=0x00 PREC=0x00 TTL=107 ID=4384 PROTO=UDP SPT=2368 "
        "DPT=1434 LEN=384"
    )

    test_record_1.sig_text = (
        " <+>sendmail</+> gB9HwAC16191: <+>to</+>  <+>ctladdr</+>  (0/0), <+>delay</+>  "
        "<+>xdelay</+>  <+>mailer</+>  <+>pri</+>  <+>dsn</+>  <+>stat</+>  <+>did</+> "
        "<+>not</+> <+>issue</+> MAIL/EXPN/VRFY/ETRN <+>during</+>  <+>xinetd</+> "
        "<+>Version</+> 2.3.10, [pulseaudio] pid.c: <+>Daemon</+> <+>already</+> running. "
        "<+>DHCPREQUEST</+> <+>of</+> 11.22.233.244 <+>on</+> eno1 <+>to</+> 11.22.33.44 "
        "<+>port</+> 67 (xid= <+>Failed</+> <+>password</+> <+>for</+> <+>root</+> <+>from</+> "
        "111.222.233.244 <+>port</+> 40757 ssh2, <+>authentication</+> failure; <+>logname</+>  "
        "<+>uid</+>  <+>euid</+>  <+>tty</+>  <+>ruser</+>  <+>rhost</+>   <+>user</+>  "
        "<+>to</+>  <+>ctladdr</+>  (0/0), <+>delay</+>  <+>xdelay</+>  <+>mailer</+>  "
        "<+>pri</+>  <+>dsn</+>  [Classification: <+>Potential</+> <+>Corporate</+> "
        "<+>Privacy</+> Violation] [Priority: 1]: {TCP} 11.22.33.44:1060 -> 111.222.23.2:1234, "
        "<+>Closed</+> <+>dest</+> <+>port</+> <+>used</+>  <+>local</+> <+>dest</+>  "
        "<+>syn</+>  0.9550 {TCP} 111.222.23.26:2222 -> 11.22.33.44:8000, <+>IN</+>  "
        "<+>PHYSIN</+>  <+>OUT</+>  <+>PHYSOUT</+>  <+>SRC</+>  <+>DST</+>  <+>LEN</+>  "
        "<+>TOS</+>  <+>PREC</+>  <+>TTL</+>  <+>ID</+>  "
        "<+>PROTO</+>  <+>SPT</+>  <+>DPT</+>  <+>LEN</+> "
    )

    test_record_1.sig_list = [
        "<+>sendmail</+>",
        "<+>to</+>",
        "<+>ctladdr</+>",
        "<+>delay</+>",
        "<+>xdelay</+>",
        "<+>mailer</+>",
        "<+>pri</+>",
        "<+>dsn</+>",
        "<+>stat</+>",
        "<+>did</+>",
        "<+>not</+>",
        "<+>issue</+>",
        "<+>during</+>",
        "<+>xinetd</+>",
        "<+>Version</+>",
        "<+>Daemon</+>",
        "<+>already</+>",
        "<+>DHCPREQUEST</+>",
        "<+>of</+>",
        "<+>on</+>",
        "<+>to</+>",
        "<+>port</+>",
        "<+>Failed</+>",
        "<+>password</+>",
        "<+>for</+>",
        "<+>root</+>",
        "<+>from</+>",
        "<+>port</+>",
        "<+>authentication</+>",
        "<+>logname</+>",
        "<+>uid</+>",
        "<+>euid</+>",
        "<+>tty</+>",
        "<+>ruser</+>",
        "<+>rhost</+>",
        "<+>user</+>",
        "<+>to</+>",
        "<+>ctladdr</+>",
        "<+>delay</+>",
        "<+>xdelay</+>",
        "<+>mailer</+>",
        "<+>pri</+>",
        "<+>dsn</+>",
        "<+>Potential</+>",
        "<+>Corporate</+>",
        "<+>Privacy</+>",
        "<+>Closed</+>",
        "<+>dest</+>",
        "<+>port</+>",
        "<+>used</+>",
        "<+>local</+>",
        "<+>dest</+>",
        "<+>syn</+>",
        "<+>IN</+>",
        "<+>PHYSIN</+>",
        "<+>OUT</+>",
        "<+>PHYSOUT</+>",
        "<+>SRC</+>",
        "<+>DST</+>",
        "<+>LEN</+>",
        "<+>TOS</+>",
        "<+>PREC</+>",
        "<+>TTL</+>",
        "<+>ID</+>",
        "<+>PROTO</+>",
        "<+>SPT</+>",
        "<+>DPT</+>",
        "<+>LEN</+>",
    ]

    test_record_1.sig_str_brackets = (
        "<+>sendmail</+> <+>to</+> <+>ctladdr</+> <+>delay</+> <+>xdelay</+> <+>mailer</+> "
        "<+>pri</+> <+>dsn</+> <+>stat</+> <+>did</+> <+>not</+> <+>issue</+> <+>during</+> "
        "<+>xinetd</+> <+>Version</+> <+>Daemon</+> <+>already</+> <+>DHCPREQUEST</+> <+>of</+> "
        "<+>on</+> <+>to</+> <+>port</+> <+>Failed</+> <+>password</+> <+>for</+> <+>root</+> "
        "<+>from</+> <+>port</+> <+>authentication</+> <+>logname</+> <+>uid</+> <+>euid</+> "
        "<+>tty</+> <+>ruser</+> <+>rhost</+> <+>user</+> <+>to</+> <+>ctladdr</+> <+>delay</+> "
        "<+>xdelay</+> <+>mailer</+> <+>pri</+> <+>dsn</+> <+>Potential</+> <+>Corporate</+> "
        "<+>Privacy</+> <+>Closed</+> <+>dest</+> <+>port</+> <+>used</+> <+>local</+> "
        "<+>dest</+> <+>syn</+> <+>IN</+> <+>PHYSIN</+> <+>OUT</+> <+>PHYSOUT</+> <+>SRC</+> "
        "<+>DST</+> <+>LEN</+> <+>TOS</+> <+>PREC</+> <+>TTL</+> <+>ID</+> <+>PROTO</+> "
        "<+>SPT</+> <+>DPT</+> <+>LEN</+>"
    )

    test_record_1.sig_str_no_tags = (
        "sendmail to ctladdr delay xdelay mailer pri dsn stat did not issue during xinetd "
        "Version Daemon already DHCPREQUEST of on to port Failed password for root from port "
        "authentication logname uid euid tty ruser rhost user to ctladdr delay xdelay mailer "
        "pri dsn Potential Corporate Privacy Closed dest port used local dest syn IN PHYSIN OUT "
        "PHYSOUT SRC DST LEN TOS PREC TTL ID PROTO SPT DPT LEN"
    )

    test_record_1.sig_token_pos_list = [
        [1, 16],
        [31, 40],
        [42, 56],
        [65, 77],
        [79, 92],
        [94, 107],
        [109, 119],
        [121, 131],
        [133, 144],
        [146, 156],
        [157, 167],
        [168, 180],
        [201, 214],
        [216, 229],
        [230, 244],
        [273, 286],
        [287, 301],
        [311, 329],
        [330, 339],
        [354, 363],
        [369, 378],
        [391, 402],
        [412, 425],
        [426, 441],
        [442, 452],
        [453, 464],
        [465, 476],
        [493, 504],
        [517, 538],
        [548, 562],
        [564, 574],
        [576, 587],
        [589, 599],
        [601, 613],
        [615, 627],
        [630, 641],
        [643, 652],
        [654, 668],
        [677, 689],
        [691, 704],
        [706, 719],
        [721, 731],
        [733, 743],
        [762, 778],
        [779, 795],
        [796, 810],
        [882, 895],
        [896, 907],
        [908, 919],
        [920, 931],
        [933, 945],
        [946, 957],
        [959, 969],
        [1024, 1033],
        [1035, 1048],
        [1050, 1060],
        [1062, 1076],
        [1078, 1088],
        [1090, 1100],
        [1102, 1112],
        [1114, 1124],
        [1126, 1137],
        [1139, 1149],
        [1151, 1160],
        [1162, 1174],
        [1176, 1186],
        [1188, 1198],
        [1200, 1210],
    ]

    test_log_records = [test_record_1]


class DatasetTestSignaturePhase(SimpleNamespace):
    kernel_log_1 = LogRecordTest()
    kernel_log_1.raw_text = (
        "Mar  9 12:31:34 bridge kernel: INBOUND UDP: IN=br0 PHYSIN=eth0 OUT=br0 PHYSOUT=eth1 "
        "SRC=100.113.134.76 DST=11.22.33.44 LEN=404 TOS=0x00 PREC=0x00 TTL=107 ID=4384 PROTO=UDP "
        "SPT=2368 DPT=1434 LEN=384"
    )
    kernel_log_1.number = 1
    kernel_log_1.sig_list = [
        "<+>kernel</+>",
        "<+>INBOUND</+>",
        "<+>UDP</+>",
        "<+>IN</+>",
        "<+>PHYSIN</+>",
        "<+>OUT</+>",
        "<+>PHYSOUT</+>",
        "<+>SRC</+>",
        "<+>DST</+>",
        "<+>LEN</+>",
        "<+>TOS</+>",
        "<+>PREC</+>",
        "<+>TTL</+>",
        "<+>ID</+>",
        "<+>PROTO</+>",
        "<+>SPT</+>",
        "<+>DPT</+>",
        "<+>LEN</+>",
    ]

    kernel_log_2 = LogRecordTest()
    kernel_log_2.raw_text = (
        "Mar 14 16:24:46 bridge kernel: INBOUND UDP: IN=br0 PHYSIN=eth0 OUT=br0 PHYSOUT=eth1 "
        "SRC=55.165.3.129 DST=11.22.33.44 LEN=78 TOS=0x00 PREC=0x00 TTL=113 ID=38911 PROTO=UDP "
        "SPT=1033 DPT=137 LEN=58"
    )
    kernel_log_2.number = 2
    kernel_log_2.sig_list = [
        "<+>kernel</+>",
        "<+>INBOUND</+>",
        "<+>UDP</+>",
        "<+>IN</+>",
        "<+>PHYSIN</+>",
        "<+>OUT</+>",
        "<+>PHYSOUT</+>",
        "<+>SRC</+>",
        "<+>DST</+>",
        "<+>LEN</+>",
        "<+>TOS</+>",
        "<+>PREC</+>",
        "<+>TTL</+>",
        "<+>ID</+>",
        "<+>PROTO</+>",
        "<+>SPT</+>",
        "<+>DPT</+>",
        "<+>LEN</+>",
    ]

    sendmail_log_1 = LogRecordTest()
    sendmail_log_1.raw_text = (
        "Mar 14 23:47:46 combo sendmail[12661]: j2F4lk6S012661: [111.222.23.29] did not issue "
        "MAIL/EXPN/VRFY/ETRN during connection to MTA"
    )
    sendmail_log_1.number = 6
    sendmail_log_1.sig_list = [
        "<+>sendmail</+>",
        "<+>did</+>",
        "<+>not</+>",
        "<+>issue</+>",
        "<+>during</+>",
        "<+>connection</+>",
        "<+>to</+>",
        "<+>MTA</+>",
    ]

    sendmail_log_2 = LogRecordTest()
    sendmail_log_2.raw_text = (
        "Mar 16 06:04:43 combo sendmail[16489]: j2GB4h6S016489: [11.22.33.44] did not issue "
        "MAIL/EXPN/VRFY/ETRN during connection to MTA"
    )
    sendmail_log_2.number = 8
    sendmail_log_2.sig_list = [
        "<+>sendmail</+>",
        "<+>did</+>",
        "<+>not</+>",
        "<+>issue</+>",
        "<+>during</+>",
        "<+>connection</+>",
        "<+>to</+>",
        "<+>MTA</+>",
    ]

    sshd_log_1 = LogRecordTest()
    sshd_log_1.raw_text = (
        "Mar  9 12:58:12 combo sshd(pam_unix)[15021]: session opened for user test by (uid=508)"
    )
    sshd_log_1.number = 9
    sshd_log_1.sig_list = [
        "<+>sshd(pam_unix)</+>",
        "<+>session</+>",
        "<+>opened</+>",
        "<+>for</+>",
        "<+>user</+>",
        "<+>test</+>",
        "<+>by</+>",
    ]

    sshd_log_2 = LogRecordTest()
    sshd_log_2.raw_text = (
        "Mar  9 12:58:12 combo sshd(pam_unix)[15022]: session opened for user test by (uid=508)"
    )
    sshd_log_2.number = 10
    sshd_log_2.sig_list = [
        "<+>sshd(pam_unix)</+>",
        "<+>session</+>",
        "<+>opened</+>",
        "<+>for</+>",
        "<+>user</+>",
        "<+>test</+>",
        "<+>by</+>",
    ]

    log_record_list = (
        kernel_log_1,
        kernel_log_2,
        sendmail_log_1,
        sendmail_log_2,
        sshd_log_1,
        sshd_log_2,
    )
    log_records = collections.OrderedDict()

    for log_record in log_record_list:
        log_records[log_record.number] = LogRecord(
            raw_text=log_record.raw_text, number=log_record.number
        )

    mapping_signature_lognumber = defaultdict(list)
    for log_record in log_record_list:
        mapping_signature_lognumber[" ".join(log_record.sig_list)].append(log_record.number)
    mapping_signature_lognumber = collections.OrderedDict(
        sorted(mapping_signature_lognumber.items())
    )


class SignatureRulesTest:
    start_tag = "<+>"
    end_tag = "</+>"

    rule_1 = SignatureRule(
        pattern=re.compile(r"\w{3}\s? \d{1,2} \d{2}:\d{2}:\d{2} \S{0,55} (\S*?)\[?\d{0,5}\]?:"),
        repl=r" <+>\1</+>",
        description="mark src-name of syslog header",
    )
    rule_2 = SignatureRule(
        pattern=re.compile(r"(=)\S+"),
        repl=r"\1",
        description="delete all values of attribute=value pairs",
    )
    rule_3 = SignatureRule(
        pattern=re.compile(r" ([a-zA-Z*]{1,30})[ |=|:|,]"),
        repl=r" <+>\1</+> ",
        description="mark all words",
    )
    rule_4 = SignatureRule(
        pattern=re.compile(r" ([a-zA-Z*]{1,30})$"),
        repl=r" <+>\1</+> ",
        description="mark last word of log_text",
    )


class LogSaltModeTestComposition(SimpleNamespace):
    rules = [
        SignatureRulesTest.rule_1,
        SignatureRulesTest.rule_2,
        SignatureRulesTest.rule_3,
        SignatureRulesTest.rule_4,
    ]
