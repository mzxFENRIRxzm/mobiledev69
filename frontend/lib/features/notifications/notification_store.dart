import 'dart:async';
import 'package:flutter/widgets.dart';
import '../../core/api/api_service.dart';

class NotificationStore extends ChangeNotifier with WidgetsBindingObserver {
  final ApiService api;
  NotificationStore(this.api) {
    WidgetsBinding.instance.addObserver(this);
  }
  bool _foreground = true;
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (_foreground) refresh();
  }

  List<Map<String, dynamic>> items = [];
  int unread = 0, latestId = 0, announcement = 0;
  String? error, _account;
  Timer? _timer;
  int _generation = 0;
  bool _loading = false, _initialized = false, _disposed = false;

  void setAccount(String? account) {
    if (account == _account) return;
    _account = account;
    _generation++;
    _timer?.cancel();
    items = [];
    unread = latestId = 0;
    error = null;
    _loading = _initialized = false;
    notifyListeners();
    if (account != null) {
      refresh();
      _timer = Timer.periodic(const Duration(seconds: 5), (_) => refresh());
    }
  }

  Future<void> refresh() async {
    if (_disposed || _account == null || _loading || !_foreground) return;
    final ticket = _generation;
    _loading = true;
    try {
      final result = await api.request('notifications/');
      if (_disposed || ticket != _generation) return;
      final next = (result['results'] as List).cast<Map<String, dynamic>>();
      final newest = result['latest_id'] as int;
      if (_initialized &&
          next.any(
            (n) => n['read_at'] == null && (n['id'] as int) > latestId,
          )) {
        announcement++;
      }
      items = next;
      unread = result['unread_count'] as int;
      latestId = newest;
      error = null;
      _initialized = true;
    } catch (_) {
      if (!_disposed && ticket == _generation) {
        error = 'ยังโหลดการแจ้งเตือนไม่ได้ กำลังลองเชื่อมต่อใหม่';
      }
    } finally {
      if (!_disposed && ticket == _generation) {
        _loading = false;
        notifyListeners();
      }
    }
  }

  Future<void> markRead(int id) async {
    await api.request('notifications/$id/read/', method: 'POST');
    await refresh();
  }

  Future<void> markAllRead() async {
    await api.request(
      'notifications/read-all/',
      method: 'POST',
      data: {'through_id': latestId},
    );
    await refresh();
  }

  @override
  void dispose() {
    _disposed = true;
    _timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}
