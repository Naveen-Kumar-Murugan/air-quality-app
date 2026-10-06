import 'package:amazon_cognito_identity_dart_2/cognito.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';
import 'dart:math';
import '../../core/config.dart';

class AuthService {
  final _storage = const FlutterSecureStorage();
  late final CognitoUserPool _userPool;

  AuthService() {
    _userPool = CognitoUserPool(Config.userPoolId, Config.clientId);
  }

  Future<String> signInAsGuest() async {
    String? username = await _storage.read(key: 'guest_username');
    String? password = await _storage.read(key: 'guest_password');

    if (username == null || password == null) {
      username = 'guest_${const Uuid().v4()}';
      password = _generatePassword();

      final userAttributes = <AttributeArg>[];
      try {
        await _userPool.signUp(username, password, userAttributes: userAttributes);
        print('Guest user signed up: $username');
      } catch (e) {
        print('Sign up error (might already exist): $e');
      }

      await _storage.write(key: 'guest_username', value: username);
      await _storage.write(key: 'guest_password', value: password);
    }

    final cognitoUser = CognitoUser(username, _userPool);
    final authDetails = AuthenticationDetails(
      username: username,
      password: password,
    );

    try {
      final session = await cognitoUser.authenticateUser(authDetails);
      final idToken = session?.getIdToken().getJwtToken();

      if (idToken == null) {
        throw Exception('Failed to get ID token');
      }

      await _storage.write(key: 'id_token', value: idToken);
      return idToken;
    } catch (e) {
      print('Sign in error: $e');
      rethrow;
    }
  }

  Future<String?> getToken() async {
    return await _storage.read(key: 'id_token');
  }

  String _generatePassword() {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    final random = Random.secure();
    return List.generate(24, (_) => chars[random.nextInt(chars.length)]).join();
  }
}
