import 'dart:convert';
import 'dart:math';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:openid_client/openid_client.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config.dart';
import 'auth_storage_base.dart';

class AuthService {
  final AuthStorage storage;
  Credential? _credential;
  Future<String>? _refresh;
  AuthService(FlutterSecureStorage storage) : storage = SecureAuthStorage(storage);
  AuthService.withStorage(this.storage);

  String _random() => base64UrlEncode(
    List.generate(48, (_) => Random.secure().nextInt(256)),
  ).replaceAll('=', '');

  Future<Flow> _flow(String state, String verifier) async {
    final issuer = await Issuer.discover(
      Uri.parse(issuerUrl),
    ).timeout(const Duration(seconds: 30));
    return Flow.authorizationCodeWithPKCE(
      Client(issuer, clientId),
      state: state,
      codeVerifier: verifier,
      prompt: 'login',
      scopes: ['openid', 'profile', 'email'],
    )..redirectUri = Uri.parse('$frontendUrl/callback');
  }

  Future<void> login() async {
    final state = _random();
    final verifier = _random();
    final flow = await _flow(state, verifier);
    await storage.write(
      key: 'the_x_pending',
      value: jsonEncode({
        'state': state,
        'verifier': verifier,
        'created': DateTime.now().millisecondsSinceEpoch,
      }),
    );
    if (!await launchUrl(flow.authenticationUri, webOnlyWindowName: '_self')) {
      throw StateError('Cannot open login');
    }
  }

  Future<bool> restore(Uri location) async {
    if (location.path == '/callback') {
      final pending = await storage.read(key: 'the_x_pending');
      await storage.delete(key: 'the_x_pending');
      if (pending == null || location.queryParameters.containsKey('error')) {
        throw StateError('Login cancelled or expired');
      }
      final data = jsonDecode(pending) as Map<String, dynamic>;
      if (DateTime.now().millisecondsSinceEpoch - (data['created'] as int) >
              600000 ||
          location.queryParameters['state'] != data['state'] ||
          !location.queryParameters.containsKey('code')) {
        throw StateError('Invalid callback');
      }
      final flow = await _flow(data['state'], data['verifier']);
      final credential = await flow
          .callback(location.queryParameters)
          .timeout(const Duration(seconds: 30));
      final errors = await credential.validateToken().toList().timeout(
        const Duration(seconds: 30),
      );
      if (errors.isNotEmpty) throw StateError('Invalid identity token');
      _credential = credential;
      await _persist();
    } else {
      final saved = await storage.read(key: 'the_x_session');
      if (saved == null) return false;
      _credential = Credential.fromJson(jsonDecode(saved));
      if (_credential!.client.clientId != clientId ||
          _credential!.client.issuer.metadata.issuer.toString().replaceAll(
                RegExp(r'/$'),
                '',
              ) !=
              issuerUrl) {
        await clear();
        return false;
      }
    }
    return true;
  }

  Future<void> _persist() => storage.write(
    key: 'the_x_session',
    value: jsonEncode(_credential!.toJson()),
  );

  Future<String> accessToken() =>
      _refresh ??= _getToken().whenComplete(() => _refresh = null);
  Future<String> _getToken() async {
    if (_credential == null) throw StateError('Not authenticated');
    final token = await _credential!.getTokenResponse().timeout(
      const Duration(seconds: 30),
    );
    await _persist();
    if (token.accessToken == null) throw StateError('Missing access token');
    return token.accessToken!;
  }

  Uri? logoutUri() => _credential?.generateLogoutUrl(
    redirectUri: Uri.parse('$frontendUrl/login'),
  );
  Future<void> clear() async {
    _credential = null;
    await storage.delete(key: 'the_x_session');
    await storage.delete(key: 'the_x_pending');
  }

  Future<void> endProviderSession(Uri? uri) async {
    if (uri != null) await launchUrl(uri, webOnlyWindowName: '_self');
  }
}
