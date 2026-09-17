import 'package:flutter/foundation.dart';
import '../../../core/result.dart';
import '../data/garage_repository.dart';
import '../domain/motorcycle.dart';

class GarageViewModel extends ChangeNotifier {
  final GarageRepository repository;
  List<Motorcycle> motorcycles = [];
  bool loading = false;
  String? error;
  String query = '';
  GarageViewModel(this.repository);
  List<Motorcycle> get filtered => motorcycles
      .where(
        (bike) => '${bike.brand} ${bike.model} ${bike.plate}'
            .toLowerCase()
            .contains(query.toLowerCase()),
      )
      .toList();
  void search(String value) {
    query = value;
    notifyListeners();
  }

  Future<void> load() async {
    loading = true;
    error = null;
    notifyListeners();
    final result = await repository.list();
    if (result is Success<List<Motorcycle>>) motorcycles = result.value;
    if (result is Failure<List<Motorcycle>>) error = result.message;
    loading = false;
    notifyListeners();
  }

  Future<bool> save(Map<String, dynamic> data, {int? id}) async {
    final result = await repository.save(data, id: id);
    if (result is Failure<void>) {
      error = result.message;
      notifyListeners();
      return false;
    }
    await load();
    return true;
  }

  Future<void> delete(int id) async {
    final result = await repository.delete(id);
    if (result is Failure<void>) {
      error = result.message;
      notifyListeners();
    } else {
      await load();
    }
  }
}
