# HTTP एक्सेस लॉग — दायरा और सीमाएँ

> **प्राथमिक:** SKOPOS एनालिटिक्स **nginx एक्सेस लॉग** के लिए बनाए गए हैं। **Apache combined** प्रारूप स्पष्ट रूप से सक्षम होने पर (`apache.enabled: true`) भी समर्थित है।

## समर्थित

| स्रोत | कैसे |
|------|--------|
| होस्ट पर nginx एक्सेस लॉग फ़ाइलें | `ssh_nginx_access_log` या `ssh_http_access_log` + `nginx.access_log_path` |
| Apache एक्सेस लॉग फ़ाइलें (combined) | `ssh_http_access_log` + `apache.enabled: true` |
| अतिरिक्त nginx लॉग | `access_log_paths` या `auto_discover_logs` |
| अतिरिक्त Apache लॉग | `apache.access_log_paths` या `apache.auto_discover_logs` |
| Docker कंटेनर stdout (वैकल्पिक) | केवल जब `auto_discover_docker_logs: true`; पार्सर पहले **combined**, फिर **uvicorn** आज़माता है |

## प्राथमिक एनालिटिक्स के रूप में असमर्थित

- स्वतंत्र लॉग स्रोत के रूप में Caddy / Traefik
- combined-आकार की पंक्तियों के बिना क्लाउड CDN लॉग (Cloudflare, Fastly)
- HTTP एक्सेस पंक्तियों के बिना एप्लिकेशन लॉग

यदि आप nginx पर TLS समाप्त करके Node/Python को प्रॉक्सी करते हैं, **nginx एक्सेस लॉगिंग सक्षम रखें** — यह प्रोडक्शन फ़्लीट के लिए प्रामाणिक ट्रैफ़िक रिकॉर्ड रहता है।

## Apache (परीक्षण / द्वितीयक)

Apache को **combined** लॉग प्रारूप (nginx combined जैसे फ़ील्ड) का उपयोग करना चाहिए। उदाहरण:

```apache
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
CustomLog /var/log/apache2/access.log combined
```

metis पर, परीक्षण httpd कंटेनर nginx 80/443 के साथ **8088** पर चल सकता है — `metis/deploy/apache-test/` देखें।

### एडमिन पैनल स्मोक टेस्ट

1. डिप्लॉय: metis होस्ट पर `./metis/deploy/apache-test/deploy.sh`।
2. ट्रैफ़िक जनरेट करें:
   ```bash
curl -sS http://127.0.0.1:8088/
curl -sS http://127.0.0.1:8088/admin/
curl -sS "http://127.0.0.1:8088/admin/?page=settings"
tail -n 5 /opt/metis/deploy/apache-test/logs/access_log
```
3. `servers.yaml` में: `source: ssh_http_access_log`, `apache.enabled: true`, `access_log` का पथ।
4. SKOPOS **एनालिटिक्स** में, `/admin` वाले पथ फ़िल्टर करें — collect के बाद पंक्तियाँ दिखनी चाहिए।

Apache एडमिन रूट **परीक्षण फ़िक्स्चर** हैं; प्रोडक्शन फ़्लीट को अभी भी nginx एक्सेस लॉग को प्रामाणिक मानना चाहिए।

## अनुशंसित nginx `log_format`

कम से कम शामिल करें: `$remote_addr`, `$time_local`, `$request`, `$status`, `$body_bytes_sent`, `$http_referer`, `$http_user_agent`। प्रति-vhost एनालिटिक्स के लिए **`$host`** जोड़ें:

```nginx
log_format skopos '$remote_addr - $remote_user [$time_local] '
                  '"$request" $status $body_bytes_sent '
                  '"$http_referer" "$http_user_agent" "$host"';
access_log /var/log/nginx/access.log skopos;
```

## nginx-पहले क्यों?

- फ़्लीट में पूर्वानुमेय combined लॉग प्रारूप
- प्रत्येक बॉक्स पर एजेंट इंस्टॉल किए बिना `/var/log/nginx/` का SSH tail
- मिश्रित स्टैक या परीक्षण नोड्स के लिए Apache वैकल्पिक
- सुरक्षा मॉड्यूल वेब स्टैक से स्वतंत्र रूप से OS मेट्रिक्स जाँचता है
