import requests
from cryptography import x509

with requests.get("https://www.google.com", stream=True) as response:
    certificate_info = response.raw.connection.sock.getpeercert()
    certificate_info_raw = response.raw.connection.sock.getpeercert(True)
    certificate = x509.load_der_x509_certificate(certificate_info_raw)
    if certificate_info and "crlDistributionPoints" in certificate_info:
        print(certificate_info["crlDistributionPoints"])
        http_crl = [
            crl for crl in certificate_info["crlDistributionPoints"] if crl.startswith("http")
        ]
        http_crl = http_crl[0] if http_crl else None
        if http_crl:
            with requests.get(http_crl) as crl_response:
                crl = x509.load_der_x509_crl(crl_response.content)
                revoked = crl.get_revoked_certificate_by_serial_number(certificate.serial_number)
                if revoked:
                    print("Certificate is revoked")
                else:
                    print("Certificate is not revoked")
    else:
        print("No CRL distribution points found")
