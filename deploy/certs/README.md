# T-Bank package registry certificates

The image installs `t-tech-investments` from T-Bank's official package
registry. As checked on 1 October 2026, the registry presents a certificate
issued by Russian Trusted Sub CA but does not send that intermediate
certificate. Standard Debian/Python CA bundles cannot validate the incomplete
chain.

`RussianTrustedRootCA.pem` came from the installed T-Invest SDK's bundled
certificate. `RussianTrustedSubCA.pem` came from the CA Issuers URL in the
registry's leaf certificate:
`http://nuc-cdp.digital.gov.ru/cdp/subca_ssl_rsa2024.crt`.
The intermediate was verified against the bundled root, and the registry leaf
was verified against the intermediate and root. SHA-256 certificate fingerprints:

- Root: `D2:6D:2D:02:31:B7:C3:9F:92:CC:73:85:12:BA:54:10:35:19:E4:40:5D:68:B5:BD:70:3E:97:88:CA:8E:CF:31`
- Intermediate: `21:55:78:50:36:C9:00:DB:B5:F1:BB:2A:15:69:C8:0C:55:59:5B:D6:BF:94:86:7A:29:BB:DD:BC:7D:88:A3:F2`

The Dockerfile uses these certificates only for `pip install` during the image
build. It does not add them to the runtime system trust store. If the registry
rotates certificates, inspect and validate the new chain before updating these
files.
