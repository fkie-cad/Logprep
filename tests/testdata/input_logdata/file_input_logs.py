# pylint: disable=line-too-long

test_initial_log_data = [
    "Jan 19 06:50:30 computer gdm-password]: gkr-pam: unable to locate daemon control file",
    "Jan 19 06:50:30 computer gdm-password]: gkr-pam: stashed password to try later in open session",
    "Jan 19 06:50:30 computer gdm-password]: pam_unix(gdm-password:session): session opened for user user(uid=1000) by (uid=0)",
    "Jan 19 06:50:30 computer systemd-logind[881]: New session 4 of user user.",
    "Jan 19 06:50:30 computer systemd: pam_unix(systemd-user:session): session opened for user user(uid=1000) by (uid=0)",
    "Jan 19 06:50:30 computer gdm-password]: gkr-pam: gnome-keyring-daemon started properly and unlocked keyring",
    "Jan 19 06:50:43 computer polkitd(authority=local): Unregistered Authentication Agent for unix-session:c1 (system bus name :1.50, object path /org/freedesktop/PolicyKit1/AuthenticationAgent, locale en_US.UTF-8) (disconnected from bus)",
    "Jan 19 06:50:43 computer gdm-launch-environment]: pam_unix(gdm-launch-environment:session): session closed for user gdm",
    "Jan 19 06:50:43 computer systemd-logind[881]: Session c1 logged out. Waiting for processes to exit.",
    "Jan 19 06:50:43 computer systemd-logind[881]: Removed session c1.",
]

test_rotated_log_data = [
    "Jan 19 08:28:41 computer su: pam_unix(su:session): session opened for user root(uid=0) by user(uid=0)",
    "Jan 19 08:29:09 computer su: pam_unix(su:session): session closed for user root",
    "Jan 19 08:29:09 computer sudo: pam_unix(sudo:session): session closed for user root",
    "Jan 19 08:30:01 computer CRON[186745]: pam_unix(cron:session): session opened for user root(uid=0) by (uid=0)",
    "Jan 19 08:30:01 computer CRON[186745]: pam_unix(cron:session): session closed for user root",
]

test_rotated_log_data_less_256 = [
    "Jan 19 08:29:09 computer sudo: pam_unix(sudo:session): session closed for user root"
]
