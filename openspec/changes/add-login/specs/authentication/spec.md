# Authentication Capability

## Requirement: Email Password Login

Users can log in with email and password credentials.

### Scenario: Successful login

Given a registered user with email "user@example.com"
When the user submits valid credentials
Then the system returns an access token
And the user is redirected to the dashboard

### Scenario: Invalid password

Given a registered user with email "user@example.com"
When the user submits an incorrect password
Then the system returns a 401 error
And the login attempt is logged

## Requirement: Password Reset

Users can reset their password via email verification.

### Scenario: Request password reset

Given a registered user
When the user requests a password reset
Then a reset link is sent to their email
