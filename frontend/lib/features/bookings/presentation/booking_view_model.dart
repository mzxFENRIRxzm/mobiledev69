import 'package:flutter/foundation.dart';
import '../../../core/result.dart';
import '../data/booking_repository.dart';
import '../domain/booking.dart';

class BookingViewModel extends ChangeNotifier {
  final BookingRepository repository;
  BookingViewModel(this.repository);
  List<Booking> bookings = [];
  bool loading = false, busy = false;
  String? error;
  bool _disposed = false;
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
    if (result is Success<List<Booking>>) bookings = result.value;
    if (result is Failure<List<Booking>>) error = result.message;
    loading = false;
    _notify();
  }

  Future<String?> _save(Future<Result<void>> Function() operation) async {
    if (busy) return 'กำลังดำเนินการ';
    busy = true;
    _notify();
    final result = await operation();
    final message = result is Failure<void> ? result.message : null;
    await load();
    if (message != null) error = message;
    busy = false;
    _notify();
    return message;
  }

  Future<String?> create(
    int motorcycle,
    DateTime date,
    String problem,
    int shop,
  ) => _save(() => repository.create(motorcycle, date, problem, shop));
  Future<String?> transition(int id, String action, String notes) =>
      _save(() => repository.transition(id, action, notes));
}
