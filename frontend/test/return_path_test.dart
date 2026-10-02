import 'package:flutter_test/flutter_test.dart';
import 'package:the_x/core/auth/return_path.dart';

void main() {
  test('return paths preserve internal query parameters only', () {
    expect(
      safeReturnPath('/messages?conversation=2'),
      '/messages?conversation=2',
    );
    expect(safeReturnPath('/bookings?shop=3'), '/bookings?shop=3');
    expect(safeReturnPath('/admin-dashboard'), '/admin-dashboard');
    for (final path in [
      'https://evil.test',
      '//evil.test/messages',
      '/callback?code=secret',
      '/loading',
      '/unknown',
      '/admin',
    ]) {
      expect(safeReturnPath(path), isNull);
    }
  });
}
