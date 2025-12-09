"""DNS Authenticator for Contabo DNS."""

import logging
import uuid
import requests

from certbot import errors
from certbot.plugins import dns_common

logger = logging.getLogger(__name__)

CONTABO_AUTH_URL = "https://auth.contabo.com/auth/realms/contabo/protocol/openid-connect/token"
CONTABO_API_URL = "https://api.contabo.com/v1"


class Authenticator(dns_common.DNSAuthenticator):
    """DNS Authenticator for Contabo DNS
    
    This Authenticator uses the Contabo API to fulfill a dns-01 challenge.
    """

    description = "Obtain certificates using a DNS TXT record (if you are using Contabo for DNS)."
    ttl = 60

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.credentials = None
        self._token = None

    @classmethod
    def add_parser_arguments(cls, add):
        super().add_parser_arguments(add, default_propagation_seconds=120)
        add("credentials", help="Contabo credentials INI file.")

    def more_info(self):
        return (
            "This plugin configures a DNS TXT record to respond to a dns-01 challenge using "
            "the Contabo API."
        )

    def _setup_credentials(self):
        self.credentials = self._configure_credentials(
            "credentials",
            "Contabo credentials INI file",
            {
                "client_id": "Client ID for Contabo API",
                "client_secret": "Client Secret for Contabo API", 
                "api_user": "API User (email) for Contabo API",
                "api_password": "API Password for Contabo API",
            },
        )

    def _get_token(self):
        """Get OAuth2 access token from Contabo."""
        if self._token:
            return self._token
            
        data = {
            "grant_type": "password",
            "client_id": self.credentials.conf("client_id"),
            "client_secret": self.credentials.conf("client_secret"),
            "username": self.credentials.conf("api_user"),
            "password": self.credentials.conf("api_password"),
        }
        
        try:
            response = requests.post(CONTABO_AUTH_URL, data=data, timeout=30)
            response.raise_for_status()
            self._token = response.json().get("access_token")
            if not self._token:
                raise errors.PluginError("Failed to get access token from Contabo")
            return self._token
        except requests.exceptions.RequestException as e:
            raise errors.PluginError(f"Error authenticating with Contabo: {e}")

    def _get_headers(self):
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "x-request-id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }

    def _find_zone(self, domain):
        """Find the DNS zone for a given domain."""
        headers = self._get_headers()
        
        try:
            response = requests.get(
                f"{CONTABO_API_URL}/dns/zones",
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            zones_data = response.json()
            
            zones = []
            if "data" in zones_data:
                zones = [z.get("zoneName") for z in zones_data["data"] if z.get("zoneName")]
            
            # Find the best matching zone
            domain_parts = domain.rstrip('.').split('.')
            for i in range(len(domain_parts)):
                potential_zone = '.'.join(domain_parts[i:])
                if potential_zone in zones:
                    return potential_zone
                    
            raise errors.PluginError(f"Could not find DNS zone for {domain}")
            
        except requests.exceptions.RequestException as e:
            raise errors.PluginError(f"Error listing DNS zones: {e}")

    def _perform(self, domain, validation_name, validation):
        """Create a TXT record for the validation."""
        zone = self._find_zone(validation_name)
        
        # Calculate the record name (subdomain part)
        if validation_name.rstrip('.').endswith(zone):
            record_name = validation_name.rstrip('.')[:-len(zone)-1]
        else:
            record_name = validation_name.rstrip('.')
        
        headers = self._get_headers()
        
        data = {
            "name": record_name,
            "type": "TXT",
            "ttl": self.ttl,
            "prio": 0,
            "data": validation,
        }
        
        try:
            response = requests.post(
                f"{CONTABO_API_URL}/dns/zones/{zone}/records",
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            logger.info(f"Successfully added TXT record for {validation_name}")
        except requests.exceptions.RequestException as e:
            raise errors.PluginError(f"Error adding TXT record: {e}")

    def _cleanup(self, domain, validation_name, validation):
        """Delete the TXT record after validation."""
        try:
            zone = self._find_zone(validation_name)
            
            if validation_name.rstrip('.').endswith(zone):
                record_name = validation_name.rstrip('.')[:-len(zone)-1]
            else:
                record_name = validation_name.rstrip('.')
            
            headers = self._get_headers()
            
            # List records to find the one to delete
            response = requests.get(
                f"{CONTABO_API_URL}/dns/zones/{zone}/records",
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            records_data = response.json()
            
            # Find and delete matching TXT records
            if "data" in records_data:
                for record in records_data["data"]:
                    if (record.get("name") == record_name and 
                        record.get("type") == "TXT" and
                        record.get("data") == validation):
                        
                        record_id = record.get("recordId")
                        if record_id:
                            del_response = requests.delete(
                                f"{CONTABO_API_URL}/dns/zones/{zone}/records/{record_id}",
                                headers=self._get_headers(),
                                timeout=30
                            )
                            del_response.raise_for_status()
                            logger.info(f"Successfully deleted TXT record for {validation_name}")
                            return
                            
            logger.warning(f"Could not find TXT record to delete for {validation_name}")
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error cleaning up TXT record: {e}")
