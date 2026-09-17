import '../../../core/api/api_service.dart';
import '../../../core/result.dart';
import '../domain/booking.dart';

class BookingRepository {
  final ApiService api;
  BookingRepository(this.api);
  Future<Result<List<Booking>>> list() async {
    try {
      final items = <Booking>[];
      for (var page = 1; ; page++) {
        final data = await api.request('bookings/?page=$page');
        items.addAll((data['results'] as List).map((e) => Booking.fromJson(e)));
        if (data['next'] == null) break;
      }
      return Success(items);
    } catch (e) {
      return Failure(describeError(e));
    }
  }

  Future<Result<void>> create(
    int motorcycle,
    DateTime appointment,
    String problem,
    int shop,
  ) async {
    try {
      await api.request(
        'bookings/',
        method: 'POST',
        data: {
          'motorcycle': motorcycle,
          'shop': shop,
          'appointment_at': appointment.toUtc().toIso8601String(),
          'problem': problem.trim(),
        },
      );
      return const Success(null);
    } catch (e) {
      return Failure(describeError(e));
    }
  }

  Future<Result<void>> transition(int id, String action, String notes) async {
    try {
      await api.request(
        'bookings/$id/transition/',
        method: 'POST',
        data: {
          'action': action,
          'repair_notes': action == 'complete' ? notes.trim() : '',
          'cancellation_reason': action == 'cancel' ? notes.trim() : '',
        },
      );
      return const Success(null);
    } catch (e) {
      return Failure(describeError(e));
    }
  }
}
