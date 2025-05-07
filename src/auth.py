import json
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError


@dataclass
class GetAwsSecret:
    _secret_name: str
    _region_name: str

    def get_aws_secret(self):
        """
        Retrieve a secret from AWS Secrets Manager.

        This method creates a session using a specified AWS profile and retrieves
        a secret value from AWS Secrets Manager. The secret is then parsed from
        JSON format and returned as a dictionary.

        Returns:
            dict: The secret retrieved from AWS Secrets Manager.

        Raises:
            ClientError: If there is an error retrieving the secret from AWS Secrets Manager.
        """
        session = boto3.session.Session(profile_name="default")
        client = session.client(
            service_name="secretsmanager", region_name=self._region_name
        )

        try:
            get_secret_value_response = client.get_secret_value(
                SecretId=self._secret_name
            )
        except ClientError as e:
            raise e

        secret_response = get_secret_value_response["SecretString"]
        secret = json.loads(secret_response)

        return secret
