class Config {
  static const String apiBase = String.fromEnvironment(
    'API_BASE',
    defaultValue: 'http://127.0.0.1:3000',
  );

  static const String userPoolId = String.fromEnvironment(
    'USER_POOL_ID',
    defaultValue: '',
  );

  static const String clientId = String.fromEnvironment(
    'CLIENT_ID',
    defaultValue: '',
  );

  static const String region = String.fromEnvironment(
    'REGION',
    defaultValue: 'us-east-1',
  );

  static const bool isDemo = bool.fromEnvironment('DEMO', defaultValue: false);
}
