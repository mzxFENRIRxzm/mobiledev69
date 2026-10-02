String? safeReturnPath(String? value) {
  final uri = Uri.tryParse(value ?? '');
  if (uri == null ||
      uri.hasScheme ||
      uri.hasAuthority ||
      uri.fragment.isNotEmpty) {
    return null;
  }
  const paths = [
    '/profile',
    '/admin-dashboard',
    '/messages',
    '/ai-chat',
    '/shops',
    '/bookings',
    '/jobs',
    '/garage',
  ];
  return paths.contains(uri.path) ? uri.toString() : null;
}
