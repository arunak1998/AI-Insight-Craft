#!/bin/bash

# Create User Pool
export POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name "MyMCPServerUserPool" \
  --policies '{"PasswordPolicy":{"MinimumLength":8}}' \
  --region us-east-1 | jq -r '.UserPool.Id')

echo "✅ Created User Pool: $POOL_ID"

# Create App Client
export CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-name "MyMCPClient" \
  --no-generate-secret \
  --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --region us-east-1 | jq -r '.UserPoolClient.ClientId')

echo "✅ Created App Client: $CLIENT_ID"

# Create User
aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username "mcpuser" \
  --temporary-password "TempPass123!" \
  --region us-east-1 \
  --message-action SUPPRESS > /dev/null

echo "✅ Created User: mcpuser"

# Set Permanent Password
aws cognito-idp admin-set-user-password \
  --user-pool-id $POOL_ID \
  --username "mcpuser" \
  --password "SecurePass123!" \
  --region us-east-1 \
  --permanent > /dev/null

echo "✅ Set permanent password"

# Get Bearer Token
export BEARER_TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME='mcpuser',PASSWORD='SecurePass123!' \
  --region us-east-1 | jq -r '.AuthenticationResult.AccessToken')

# Display required values
echo ""
echo "🔑 SAVE THESE VALUES - YOU'LL NEED THEM:"
echo "================================================"
echo "Pool ID: $POOL_ID"
echo "Discovery URL: https://cognito-idp.us-east-1.amazonaws.com/$POOL_ID/.well-known/openid-configuration"
echo "Client ID: $CLIENT_ID"
echo "Bearer Token: $BEARER_TOKEN"
echo "================================================"
