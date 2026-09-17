const apiBase = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://localhost:8000',
);
const issuerUrl = '$apiBase/openid';
const clientId = 'the-x-web';
const frontendUrl = String.fromEnvironment(
  'FRONTEND_URL',
  defaultValue: 'http://localhost:50000',
);
