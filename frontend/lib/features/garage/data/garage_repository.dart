import '../../../core/api/api_service.dart';
import '../../../core/result.dart';
import '../domain/motorcycle.dart';

class GarageRepository {
  final ApiService api;
  GarageRepository(this.api);
  Future<Result<List<Motorcycle>>> list() async {
    try {
      final items = <Motorcycle>[];
      int page = 1;
      while (true) {
        final data = await api.request('motorcycles/?page=$page');
        items.addAll(
          (data['results'] as List).map((e) => Motorcycle.fromJson(e)),
        );
        if (data['next'] == null) break;
        page++;
      }
      return Success(items);
    } catch (e) {
      return Failure(describeError(e));
    }
  }

  Future<Result<void>> save(Map<String, dynamic> data, {int? id}) async {
    try {
      await api.request(
        id == null ? 'motorcycles/' : 'motorcycles/$id/',
        method: id == null ? 'POST' : 'PATCH',
        data: data,
      );
      return const Success(null);
    } catch (e) {
      return Failure(describeError(e));
    }
  }

  Future<Result<void>> delete(int id) async {
    try {
      await api.request('motorcycles/$id/', method: 'DELETE');
      return const Success(null);
    } catch (e) {
      return Failure(describeError(e));
    }
  }
}
