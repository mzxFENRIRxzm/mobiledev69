import '../../../core/api/api_service.dart';
import '../../../core/result.dart';
import '../domain/shop.dart';

class ShopRepository {
  final ApiService api;
  ShopRepository(this.api);
  Future<Result<List<Shop>>> list() async {
    try {
      final items = <Shop>[];
      for (var page = 1; ; page++) {
        final data = await api.request('shops/?page=$page');
        items.addAll((data['results'] as List).map((e) => Shop.fromJson(e)));
        if (data['next'] == null) break;
      }
      return Success(items);
    } catch (e) {
      return Failure(describeError(e));
    }
  }

  Future<Result<void>> save(int id, Map<String, dynamic> data) async {
    try {
      await api.request('shops/$id/', method: 'PATCH', data: data);
      return const Success(null);
    } catch (e) {
      return Failure(describeError(e));
    }
  }
}
