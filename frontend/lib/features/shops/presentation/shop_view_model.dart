import 'package:flutter/foundation.dart';
import '../../../core/result.dart';
import '../data/shop_repository.dart';
import '../domain/shop.dart';

class ShopViewModel extends ChangeNotifier {
  final ShopRepository repository;
  ShopViewModel(this.repository);
  List<Shop> shops = [];
  bool loading = false, busy = false, _disposed = false;
  String? error;
  String query = '';
  List<Shop> get filtered => shops
      .where(
        (s) => '${s.name} ${s.address}'.toLowerCase().contains(
          query.toLowerCase().trim(),
        ),
      )
      .toList();
  void search(String value) {
    query = value;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  Future<void> load() async {
    if (loading) return;
    loading = true;
    error = null;
    _notify();
    final result = await repository.list();
    if (result is Success<List<Shop>>) shops = result.value;
    if (result is Failure<List<Shop>>) error = result.message;
    loading = false;
    _notify();
  }

  Future<String?> save(int id, Map<String, dynamic> data) async {
    if (busy || loading) return 'กำลังโหลดหรือบันทึก กรุณารอสักครู่';
    busy = true;
    _notify();
    final result = await repository.save(id, data);
    final message = result is Failure<void> ? result.message : null;
    if (message == null) {
      await load();
    } else {
      error = message;
    }
    busy = false;
    _notify();
    return message;
  }
}
