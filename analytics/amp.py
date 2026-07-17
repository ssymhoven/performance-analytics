import os
from collections import defaultdict
from os.path import dirname, abspath
from string import Template
from typing import Dict, Any

import urllib3
from source_engine.amp_source import AmpSource

urllib3.disable_warnings()


def read_query_from_file(query_file_name: str, variables: dict = None):
    file_path = os.path.join(dirname(dirname(abspath(__file__))), 'queries', query_file_name)
    with open(file_path, 'r') as file:
        query = file.read()

    # Replace placeholders with actual values
    if variables:
        template = Template(query)
        query = template.substitute(variables)

    return query


class UnauthorizedException(Exception):
    def __init__(self, message="Unauthorized"):
        self.message = message
        super().__init__(self.message)


class Amp:

    def __init__(self, client_id: str, client_secret: str, ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.amp_source = AmpSource(client_id=client_id, client_secret=client_secret)

    def _post_graphql(self, query_file: str, variables: Dict[str, Any] = defaultdict) -> Dict[str, Any]:
        """
        POST to AMP GraphQL with a retry on 401 (token refresh-once).
        """
        gql_query = read_query_from_file(query_file, variables=variables)

        return self.amp_source.post_graphql(query=gql_query)

    def get_portfolio_by_id(
            self,
            account_segment_id: int,
            portfolio_type: str = "Pre Trade Portfolio",
    ) -> Dict[str, Any]:
        """
        Calls portfolio_by_id.gql with variables:
          id: [ID!]!
          portfolioType: String!
        Returns the full GraphQL JSON response.
        """
        # If your schema expects Int/Long, convert numeric strings:
        variables = {"account_segment_id": f"[{account_segment_id}]", "portfolio_type": portfolio_type}
        return self._post_graphql("query.gql", variables=variables)
