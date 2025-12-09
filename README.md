# Certbot DNS Contabo Plugin

DNS Authenticator plugin for Certbot that uses Contabo DNS API.

## Installation

```bash
# Install dependencies first
apt install python3-pip -y

# Install the plugin from PyPI
pip3 install certbot-dns-contabo-api --break-system-packages
```

Project URL: https://pypi.org/project/certbot-dns-contabo-api/

## Configuration

### 1. Get API Credentials

From [Contabo Customer Control Panel](https://my.contabo.com/api/details), get:
- Client ID
- Client Secret
- API User (your email)
- API Password

### 2. Create Credentials File

Create `/etc/letsencrypt/contabo.ini`:

```ini
dns_contabo_client_id = YOUR_CLIENT_ID
dns_contabo_client_secret = YOUR_CLIENT_SECRET
dns_contabo_api_user = your@email.com
dns_contabo_api_password = YOUR_API_PASSWORD
```

Secure the file:

```bash
chmod 600 /etc/letsencrypt/contabo.ini
```

### 3. Issue Certificate

```bash
certbot certonly \
  --authenticator dns-contabo \
  --dns-contabo-credentials /etc/letsencrypt/contabo.ini \
  --dns-contabo-propagation-seconds 120 \
  -d example.com \
  -d "*.example.com"
```

### 4. Test Auto-Renewal

```bash
certbot renew --dry-run
```

## Credentials File Format

```ini
# Contabo API credentials
dns_contabo_client_id = your_client_id
dns_contabo_client_secret = your_client_secret
dns_contabo_api_user = your_email@example.com
dns_contabo_api_password = your_api_password
```
