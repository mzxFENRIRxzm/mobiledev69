from rest_framework import serializers


def history_page(queryset, request, serialize, size=100):
    """Opt-in cursor pagination; legacy clients retain their list response."""
    class Cursor(serializers.Serializer):
        before = serializers.IntegerField(min_value=1, required=False)
        after = serializers.IntegerField(min_value=0, required=False)
    cursor = Cursor(data=request.query_params)
    cursor.is_valid(raise_exception=True)
    values = cursor.validated_data
    if 'before' in values and 'after' in values:
        raise serializers.ValidationError('Use either before or after')
    if 'before' in values:
        queryset = queryset.filter(pk__lt=values['before'])
    if 'after' in values:
        queryset = queryset.filter(pk__gt=values['after'])
    forward = 'after' in values
    rows = list(queryset.order_by('pk' if forward else '-pk')[:size + 1])
    more = len(rows) > size
    rows = rows[:size]
    if not forward:
        rows.reverse()
    data = serialize(rows)
    if request.query_params.get('paged') != '1':
        return data
    return {'results': data, 'has_more': more,
            'cursor': (rows[-1 if forward else 0].pk if rows else None)}
