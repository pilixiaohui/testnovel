# OAuth Capability

## Requirement: OAuth2 Third-Party Login

Users can log in using third-party OAuth2 providers (Google, GitHub).

### Scenario: Google OAuth login

Given a user with a Google account
When the user clicks "Login with Google"
Then the system redirects to Google OAuth consent screen
And upon approval, creates or links the user account

## Requirement: OAuth Account Linking [REMOVED]

This requirement has been removed from scope.
