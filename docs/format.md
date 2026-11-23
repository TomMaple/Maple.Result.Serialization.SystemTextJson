# JSON Format

How `Result`, `Result<T>`, `Error`, `ErrorUri`, `ErrorDetail` and `TemplatedMessage` of [Maple.Result](https://github.com/TomMaple/Maple.Result) are written as JSON and read back. This package (*System.Text.Json*) and `Maple.Result.Serialization.NewtonsoftJson` follow this format, so a value written by one service is read the same way by another. The test vectors in [tests/TestVectors](../tests/TestVectors/README.md) are part of this specification: both packages read and write them.

The format is for values that cross a process boundary between applications that use Maple.Result: Azure Durable Functions activity inputs and outputs, Service Bus messages, stored documents. It is not the problem details format of HTTP responses ([RFC 9457](https://datatracker.ietf.org/doc/html/rfc9457)), which is described in [Problem Details Format](https://github.com/TomMaple/Maple.Result/blob/main/docs/problem-details.md) of Maple.Result.

## Contents
* [Example](#example)
* [Options](#options)
* [Result and Result&lt;T&gt;](#result-and-resultt)
* [Error](#error)
* [Values of metadata and template parameters](#values-of-metadata-and-template-parameters)
* [Type names](#type-names)
* [Equality after a round trip](#equality-after-a-round-trip)
* [Not supported](#not-supported)
* [Rules decided for this format](#rules-decided-for-this-format)

## Example
```csharp
var error = ErrorBuilder.NotFound(ErrorUri.Tag("tag:example.com,2026:orders:not-found"), "Order not found.")
    .WithDetail("Order 42 does not exist.")
    .WithInstanceUri(ErrorUri.Relative("/orders/42"))
    .WithDetailTemplated("orders.notFound", ("id", 42))
    .AddErrorDetail("/orderId", "Unknown order.")
    .WithMetadata(("retryable", false), ("limit", 100L))
    .Build();

Result<Order> result = error;
```

With the default options (no naming policy, `null` written, enums as numbers), `result` is written as:
```json
{
  "Error": {
    "Category": 3,
    "TypeUri": "tag:example.com,2026:orders:not-found",
    "Title": "Order not found.",
    "Detail": "Order 42 does not exist.",
    "InstanceUri": "/orders/42",
    "DetailTemplated": { "TemplateId": "orders.notFound", "Parameters": { "id": 42 } },
    "ErrorDetails": [ { "PropertyPointer": "/orderId", "Detail": "Unknown order.", "DetailTemplated": null } ],
    "Metadata": { "retryable": false, "limit": { "$type": "long", "$value": 100 } }
  }
}
```
(Indented here for reading; the options decide the indentation.) `42` and `false` are plain JSON, because reading them gives back an `int` and a `bool`. `100L` is wrapped, because a plain `100` would be read as an `int`.

## Options
The converters behave like the serializer does for any other type: **the options shape the JSON**. The examples use the default options, which are also the defaults of *Newtonsoft.Json*, so the two packages agree out of the box.

| Option | What it decides |
| ------ | --------------- |
| `PropertyNamingPolicy` | The member names: the .NET property names through the policy (`TypeUri`, `typeUri`, `type_uri`). |
| `DefaultIgnoreCondition` | Whether a member that is `null` is written (`Never`, the default) or omitted (`WhenWritingNull`, `WhenWritingDefault`). |
| the enum converter of the options | `Category`, `errorCategory` values and enum values: a number by default, the name with a `JsonStringEnumConverter` (and its naming policy). |
| `AllowDuplicateProperties` | A repeated member, or a repeated key of `Metadata` or `Parameters`: the last one wins (`true`, the default) or the read throws (`false`). |
| `UnmappedMemberHandling` | An unknown member of an `Error`, an `ErrorDetails` item or a `DetailTemplated` object: skipped (`Skip`, the default) or the read throws (`Disallow`). |
| `RespectNullableAnnotations` | `"ErrorDetails": null` or `"Metadata": null`: read as empty (`false`, the default) or the read throws (`true`). |

Not applied:
* `DictionaryKeyPolicy`: the keys of `Metadata` and `Parameters` are written as they are stored.
* `NumberHandling`: numbers are always JSON numbers, and numbers in strings are not read.
* `PropertyNameCaseInsensitive`: the reader always accepts a member by its name through the naming policy (exact), or by its .NET name in any case.

`WriteIndented`, the encoder, comments, trailing commas and `MaxDepth` work as usual. The names `$type`, `$comparer` and `$value` are fixed: no option changes them, and they are case-sensitive.

**What two services must share.** Two services read each other when their options are equivalent. Camel case and no naming policy always read each other (the .NET name in any case is accepted), `null` and an absent member are the same to the reader, and so are the number and the name of an enum value. A snake case, kebab case or custom naming policy on one side only cannot be read by the other, neither for the member names nor for enum names written by a `JsonStringEnumConverter` with such a policy (e.g., `"permission_denied"`), nor for custom enum member names (`[JsonStringEnumMemberName]`).

## Result and Result&lt;T&gt;
A result has either the member `Value` or the member `Error`, never both:

| Value | JSON |
| ----- | ---- |
| `Result.Success()` | `{}` |
| `Result<Order>` with a value | `{"Value":{"Id":42}}` |
| `Result<string?>` with the value `null` | `{"Value":null}` |
| `Result<int?>` with the value `null` | `{"Value":null}` |
| a failed `Result` or `Result<T>` | `{"Error":{…}}` |

* `Value` is written and read with the type info of `T` in the options (its converter, naming policy, source-generated context). It is always written, also when it is `null` and the options ignore `null` values.
* JSON `null` in place of a whole result is the `null` reference, as for every reference type.

Read; each of these throws `JsonException`, whatever `UnmappedMemberHandling` says (`{"Failure":{…}}` must never be read as a successful `Result`):
* a `Result<T>` without `Value` and without `Error` (`{}`): a missing `Value` is never `default(T)`;
* both members, in any order;
* `Value` in a `Result`;
* `"Error": null`;
* any unknown member;
* a repeated member, when `AllowDuplicateProperties` is `false`.

The member names follow the naming policy (`value`, `error` in camel case); the .NET name in any case is accepted too.

## Error
### Members
The members are written in this order:

| Member | JSON | Required | Can be `null` |
| ------ | ---- | -------- | ------------- |
| `Category` | number or name, see below | yes | no |
| `TypeUri` | string; `about:blank` is written too | yes | no |
| `Title` | string | yes | no |
| `Detail` | string | no | yes |
| `InstanceUri` | string | no | yes |
| `DetailTemplated` | object, see [Templated message](#templated-message) | no | yes |
| `ErrorDetails` | array of objects, see [Error details](#error-details) | no | no |
| `Metadata` | object, see [Values](#values-of-metadata-and-template-parameters) | no | no |

* **Required** members are always written, whatever `DefaultIgnoreCondition` says. A missing required member, or `null` for one, throws. A missing `TypeUri` is not read as `about:blank`.
* The members that **can be `null`** follow `DefaultIgnoreCondition`: with `WhenWritingNull` (or `WhenWritingDefault`) a `null` member is omitted. `null` and an absent member are read the same.
* `ErrorDetails` and `Metadata` follow the rules of the serializer for a collection that is not nullable: they are always written, also when they are empty (`[]`, `{}`). A missing one is read as empty; `null` is read as empty, unless `RespectNullableAnnotations` is `true`, then it throws.
* `Category` is written as the enum converter of the options writes `ErrorCategory`: the number by default (`3`), the name with a `JsonStringEnumConverter` (`"NotFound"`, or `"notFound"` with a camel case policy). It is read from a defined number, from a member name in any case, or from what the enum converter of the options reads. An undefined number (`99`), an unknown name (`"Unauthorized"`, the 2.x name of `PermissionDenied`) or a missing category throws; it is never read as `Validation`, the default value. The values are those of `ErrorCategory`: `Validation` 0, `Unauthenticated` 1, `PermissionDenied` 2, `NotFound` 3, `Timeout` 4, `Conflict` 5, `Failure` 6, `Critical` 7, `NotImplemented` 8, `Unavailable` 9, `LimitExceeded` 10.
* `TypeUri` and `InstanceUri` are the `Value` of the `ErrorUri`, read with `ErrorUri.Parse`, which finds the kind (`about:blank`, a relative reference starting with `/`, `tag:`, `urn:`, `http:`/`https:`, or any other scheme) and validates the value. `about:blank` is rejected as an `InstanceUri`.

Everything that the core rejects throws `JsonException`, with the exception of the core as the inner exception: a blank title, an invalid `ErrorUri` or JSON pointer, `about:blank` as the instance, a reserved metadata key (`type`, `title`, `status`, `detail`, `instance`, `errors`, `detailTemplated`, in any case), two metadata keys or two parameter names that differ only in case, a blank or padded template id, and so on. An `Error` is always built with `ErrorBuilder`, so a read never creates an error that the core would not create.

### Error details
An item of `ErrorDetails`, with its members in this order:

| Member | JSON | Required | Can be `null` |
| ------ | ---- | -------- | ------------- |
| `PropertyPointer` | string: a JSON pointer (`/orderId`, `#/items/3`, or empty for the whole input) | no | yes |
| `Detail` | string | yes | no |
| `DetailTemplated` | object, see [Templated message](#templated-message) | no | yes |

### Templated message
The `DetailTemplated` of an error or of an error detail:

| Member | JSON | Required | Can be `null` |
| ------ | ---- | -------- | ------------- |
| `TemplateId` | string | yes | no |
| `Parameters` | object, see [Values](#values-of-metadata-and-template-parameters) | no | yes |

A `TemplatedMessage` without parameters has `Parameters == null`. A `Parameters` member that is absent, `null` or `{}` is read as `Parameters == null`: the core turns an empty collection into `null`.

### Converters of their own
`ErrorUri`, `ErrorDetail` and `TemplatedMessage` have converters of their own, for members of the application's types, with the same shapes: an `ErrorUri` is a string (`"tag:example.com,2026:orders:not-found"`), an `ErrorDetail` an item of `ErrorDetails`, a `TemplatedMessage` a `DetailTemplated` object. An `ErrorUri?` that is `null` is JSON `null`; a default `ErrorUri` is `"about:blank"`. JSON `null` in place of a whole `Error`, `ErrorDetail` or `TemplatedMessage` is the `null` reference.

## Values of metadata and template parameters
The values of `Metadata` and `Parameters` are typed `object?`. JSON alone does not say which .NET type a value had, so the format adds the type where JSON loses it:

**A value is written plain exactly when reading the plain JSON gives back the same .NET type; otherwise it is wrapped** as
```json
{"$type": "<name>", "$comparer": "<name>", "$value": <json>}
```
`$comparer` is present only for a collection with a comparer that is not the default one ([Comparers](#comparers)). The writer writes the members in this order.

The keys of `Metadata` and `Parameters` are JSON member names, written as they are stored. A `null` value is always written (`DefaultIgnoreCondition` applies to members, not to the values of a dictionary).

### Plain values
| Plain JSON | Read as | Written plain for |
| ---------- | ------- | ----------------- |
| `null` | `null` | `null` |
| string | `string` | `string` |
| `true`, `false` | `bool` | `bool` |
| integer (`42`, `-7`) | `int`; outside the range of `int` it throws | `int` |
| number with a fraction or an exponent (`0.5`, `5.0`, `1e3`) | `decimal`; outside the range of `decimal` it throws | `decimal`, always with a fraction: `5m` is written as `5.0`, `5.00m` as `5.00` |
| array | `T[]`, with `T` the type of the first element; `object?[]` when the array is empty or its first element is `null` | an array that this rule gives back |
| object without a `$type` member | `Dictionary<string, V>` with the default comparer, with `V` the type of the first value; `Dictionary<string, object?>` when the object is empty or its first value is `null` | a dictionary that this rule gives back, and whose keys do not start with `$` |

* **No guessing beyond `int` and `decimal`.** A plain integer outside the range of `int` (`5000000000`) and a plain number outside the range of `decimal` (`1e30`) throw. The writer wraps every `long` and `double`, so only payloads that were not written by these converters can contain them.
* **Arrays and objects take the type of their first element.** Every element is read as a value (plain or wrapped); `T` is the type of the first one, and every later element must have exactly that type: `[1,"a"]`, `[1,2.5]`, `[1,null]` and `{"a":1,"b":"x"}` throw. `null` fits a reference type: `["a",null]` is a `string[]`. Arrays nest: `[[1,2],[3]]` is an `int[][]`, `[{"a":1}]` a `Dictionary<string,int>[]`.
* So `new[] { 1, 2 }` is written `[1,2]`, `new object?[] { null, 1 }` `[null,1]` and `new Dictionary<string, object?>()` `{}`; but `new object?[] { 1, "a" }` is wrapped as `object[]`, an empty `string[]` as `string[]`, and a `Dictionary<string, int>` with a key `$id` as `dictionary<string,int>`.

### Wrapped values
* `$type` names the .NET type ([Type names](#type-names)); `$value` is the value in the encoding of that type.
* An object with a `$type` member is a wrapper, **in any member order**: some stores (e.g., PostgreSQL `jsonb`) reorder the members of an object. A wrapper has exactly the members `$type`, `$value` and optionally `$comparer`; a missing `$value`, a repeated member or any other member throws, whatever the options say.
* Inside a typed wrapper (an array, a collection, a dictionary), the elements are written in the encoding of the element type, with no wrappers: `{"$type":"long[]","$value":[1,2]}`. Elements typed `object` are plain or wrapped one by one: `{"$type":"object[]","$value":[1,"a",{"$type":"long","$value":5}]}`.
* A wrapper is also read for a type that is written plain: `{"$type":"int","$value":5}` is the `int` 5, `{"$type":"int[]","$value":[1,2]}` an `int[]`. The writer never writes it, so writing the value back gives the plain form.
* A `$value` that is not valid for its type throws: `{"$type":"long","$value":"abc"}`, `{"$type":"char","$value":"ab"}`, `{"$type":"long[]","$value":[1,"a"]}`.

### Scalar types
Fixed names, no registration. Their `$value` is fixed by this format, not by the converters of the options.

| Name | .NET type | `$value` |
| ---- | --------- | -------- |
| `string` | `string` | string (written plain) |
| `bool` | `bool` | `true` / `false` (written plain) |
| `char` | `char` | string of exactly one UTF-16 code unit: `"a"` |
| `sbyte` `byte` `short` `ushort` `int` `uint` `long` `ulong` | the integer types | integer number: `{"$type":"long","$value":5000000000}`; outside the range of the type it throws (`int` is written plain) |
| `float` `double` | `float`, `double` | number in the shortest form that reads back to the same value (`0.1`, `1E+30`); `NaN`, `Infinity` and `-Infinity` as the strings `"NaN"`, `"Infinity"`, `"-Infinity"` |
| `decimal` | `decimal` | number, always with a fraction (written plain) |
| `guid` | `Guid` | string in the format `"D"`: `"0f8fad5b-d9cb-469f-a169-6c0a9e9e7d2c"` (lower case); other formats throw |
| `uri` | `Uri` | string: the original string, absolute or relative (`"https://example.com/a"`, `"/orders/42"`) |
| `dateTimeOffset` | `DateTimeOffset` | string in the round-trip format `"O"`: `"2026-12-01T08:30:00.0000000+01:00"` |
| `dateTime` | `DateTime` | string in the format `"O"`, which keeps the `Kind`: `"2026-12-01T08:30:00.0000000Z"` (UTC), `"2026-12-01T08:30:00.0000000"` (unspecified), `"2026-12-01T08:30:00.0000000+01:00"` (local; read as the same instant in the local time zone of the reader) |
| `dateOnly` | `DateOnly` | string in the format `"O"`: `"2026-12-01"` |
| `timeOnly` | `TimeOnly` | string in the format `"O"`: `"08:30:00.0000000"` |
| `timeSpan` | `TimeSpan` | string in the format `"c"`: `"1.02:03:04.5000000"`, `"-00:00:01"` |
| `byte[]` | `byte[]` | string in base64: `"AQID"` |

The text formats are read exactly (`ParseExact` with the invariant culture); a different format throws.

### Core types
Fixed names, no registration; they also work under Native AOT. Their `$value` is what the converter of the type writes, by the same rules as anywhere else (member names, `null` members and the category follow the options).

| Name | .NET type | Example |
| ---- | --------- | ------- |
| `error` | `Error` | `{"$type":"error","$value":{"Category":6,"TypeUri":"about:blank","Title":"Database unavailable.",…}}` for `WithMetadata("cause", innerError)` |
| `errorUri` | `ErrorUri` | `{"$type":"errorUri","$value":"/orders/42"}` |
| `errorDetail` | `ErrorDetail` | `{"$type":"errorDetail","$value":{"PropertyPointer":"/email","Detail":"Required.","DetailTemplated":null}}` |
| `templatedMessage` | `TemplatedMessage` | `{"$type":"templatedMessage","$value":{"TemplateId":"t","Parameters":null}}` |
| `errorCategory` | `ErrorCategory` | `{"$type":"errorCategory","$value":3}`, or `"NotFound"` with a `JsonStringEnumConverter` |

`Result` and `Result<T>` are not values: a result in `Metadata` or `Parameters` has no name, so the write throws.

### Arrays and nullable value types
* `T[]` for a one-dimensional array of any named `T`: `long[]`, `string[]`, `object[]`, `guid[]`, `int[][]`. Arrays with more dimensions (`int[,]`) have no name.
* `T?` for a nullable value type, as an element type: `int?[]`, `list<guid?>`; its elements are the encoding of `T` or `null`. A boxed `int?` is an `int` or `null`, so `T?` never names a value on its own.
* `object` is an element type only: `object[]`, `list<object>`, `dictionary<string,object>`; its elements are plain or wrapped one by one.

### Collections
One name for every .NET built-in collection, composed with the names of the element types (no spaces): `list<long>`, `hashSet<string>`, `dictionary<int,string>`, `list<list<int>>`, `sortedDictionary<string,guid?>`.

Generic sequences; `$value` is a JSON array:

| Name | .NET type | Order | Comparer |
| ---- | --------- | ----- | -------- |
| `list<T>` | `List<T>` | kept | |
| `hashSet<T>` | `HashSet<T>` | enumeration order | `$comparer` |
| `sortedSet<T>` | `SortedSet<T>` | sorted | `$comparer` |
| `linkedList<T>` | `LinkedList<T>` | kept | |
| `queue<T>` | `Queue<T>` | dequeue order, kept | |
| `stack<T>` | `Stack<T>` | top first, kept: the top stays on top | |
| `collection<T>` | `Collection<T>` | kept | |
| `readOnlyCollection<T>` | `ReadOnlyCollection<T>` | kept | |
| `observableCollection<T>` | `ObservableCollection<T>` | kept | |
| `immutableArray<T>` | `ImmutableArray<T>` | kept | |
| `immutableList<T>` | `ImmutableList<T>` | kept | |
| `immutableHashSet<T>` | `ImmutableHashSet<T>` | enumeration order | `$comparer` |
| `immutableSortedSet<T>` | `ImmutableSortedSet<T>` | sorted | `$comparer` |
| `immutableQueue<T>` | `ImmutableQueue<T>` | dequeue order, kept | |
| `immutableStack<T>` | `ImmutableStack<T>` | top first, kept | |
| `concurrentQueue<T>` | `ConcurrentQueue<T>` | dequeue order, kept | |
| `concurrentStack<T>` | `ConcurrentStack<T>` | top first, kept | |
| `concurrentBag<T>` | `ConcurrentBag<T>` | not kept (a bag has no order) | |

Generic maps; `$value` is a JSON object whose members are the keys:

| Name | .NET type | Order | Comparer |
| ---- | --------- | ----- | -------- |
| `dictionary<K,V>` | `Dictionary<K,V>` | enumeration order | `$comparer` (keys) |
| `sortedDictionary<K,V>` | `SortedDictionary<K,V>` | sorted | `$comparer` (keys) |
| `sortedList<K,V>` | `SortedList<K,V>` | sorted | `$comparer` (keys) |
| `orderedDictionary<K,V>` | `OrderedDictionary<K,V>` | kept | `$comparer` (keys) |
| `readOnlyDictionary<K,V>` | `ReadOnlyDictionary<K,V>` | enumeration order | not exposed: read back with the default one |
| `immutableDictionary<K,V>` | `ImmutableDictionary<K,V>` | enumeration order | `$comparer` (keys); a value comparer that is not the default one throws on write |
| `immutableSortedDictionary<K,V>` | `ImmutableSortedDictionary<K,V>` | sorted | `$comparer` (keys); a value comparer that is not the default one throws on write |
| `concurrentDictionary<K,V>` | `ConcurrentDictionary<K,V>` | enumeration order | `$comparer` (keys) |

Non-generic collections; their elements are `object` (plain or wrapped one by one), and the keys of a map must be strings: any other key throws on write.

| Name | .NET type | `$value` | Notes |
| ---- | --------- | -------- | ----- |
| `arrayList` | `ArrayList` | array | |
| `queue` | `Queue` | array | dequeue order, kept |
| `stack` | `Stack` | array | top first, kept |
| `stringCollection` | `StringCollection` | array of strings or `null` | |
| `hashtable` | `Hashtable` | object | comparer not exposed: read back with the default one |
| `sortedList` | `SortedList` | object | comparer not exposed: read back with the default one |
| `stringDictionary` | `StringDictionary` | object of strings or `null` | the type itself stores its keys in lower case |
| `nameValueCollection` | `NameValueCollection` | object whose values are arrays of strings (`{"a":["1","2"]}`) | every value of a key is kept; a `null` key throws on write; comparer not exposed |
| `listDictionary` | `ListDictionary` | object | comparer not exposed |
| `hybridDictionary` | `HybridDictionary` | object | comparer not exposed |
| `orderedDictionary` | `OrderedDictionary` | object | order kept; comparer not exposed |

* **Keys** of maps are JSON member names: a `string`, or a [scalar type](#scalar-types) in its text form (`dictionary<int,string>`: `{"1":"a"}`; `dictionary<guid,int>`: the `"D"` text). Any other key type has no name, and the write throws.
* **Order:** the elements are written in enumeration order, and read back so that the collection enumerates in the same order where the collection keeps an order. A `Stack<T>` is written top first and keeps its top (unlike the default serializer, which reverses a stack).
* A collection that is a subclass of one of these types, or any other collection type, has no name ([Type names](#type-names)). `FrozenSet<T>` and `FrozenDictionary<K,V>` are not supported: their runtime classes are internal subclasses.

### Comparers
`$comparer` is written when a collection has another comparer than the default one (`EqualityComparer<T>.Default`, `Comparer<T>.Default`, or none):

| Name | Comparer |
| ---- | -------- |
| `ordinal` | `StringComparer.Ordinal` |
| `ordinalIgnoreCase` | `StringComparer.OrdinalIgnoreCase` |
| `invariantCulture` | `StringComparer.InvariantCulture` |
| `invariantCultureIgnoreCase` | `StringComparer.InvariantCultureIgnoreCase` |
| the .NET name of a registered comparer (`MyApp.Orders.OrderIdComparer`) | a comparer registered with `ValueComparers.Add(…)` |

`StringComparer.Ordinal` is written as `ordinal`, although it behaves like the default comparer, so the read gives back the same comparer. Any other comparer (a culture-specific one such as `StringComparer.CurrentCulture`, or a custom one that is not registered) makes the write throw. A collection that does not expose its comparer is read back with the default one. An unknown `$comparer` name throws on read, and so does a `$comparer` on a type that has no comparer.

### Enums
* Named `Namespace.Name, Assembly`, the assembly name without version, culture or key: `{"$type":"MyApp.Orders.OrderStatus, MyApp","$value":2}`. A nested enum has a `+`: `MyApp.Orders.Order+Status, MyApp`.
* `$value` is written as the options write that enum: the number by default; with a `JsonStringEnumConverter`, the name, through the naming policy of the converter, and `"Read, Write"` for a combination of flags. Attributes on the enum (`[JsonConverter]`, `[JsonStringEnumMemberName]`) are respected. A value without a name is always the number. Under Native AOT, an enum that has no type info in the options is written as the number.
* Read: a number (named or not), a member name in any case, comma-separated flag names, or what the options read for that enum. An unknown name throws.
* `AddMapleResult()` resolves an enum name from a payload with `Type.GetType` and accepts the type only when it is an enum, so nothing but an enum is ever created from a name in a payload. The name is limited in length and parsed (with a small limit on its parts) before it is resolved. With `ResolveEnumsByName = false`, and always under Native AOT, only registered enums are read (`ValueTypes.Add<OrderStatus>()`, with the same name).

### Registered types
* A type registered with `ValueTypes.Add<T>()` is named by its namespace and name, the `Type.ToString()` form: `MyApp.Orders.CustomerRef`. `ValueTypes.Add<T>("MyApp.Old.CustomerRef")` adds an extra name that is read too; the first name is written.
* `$value` is written and read by the options for that type (its converter, naming policy, source-generated context): `{"$type":"MyApp.Orders.CustomerRef","$value":{"Id":7}}`.
* `JsonElement`, `JsonNode`, `StringValues` and every other type are values only when they are registered.
* Registering a type that already has a name (a scalar, a core type, a collection) does nothing; its name and encoding stay.

## Type names
* Names are case-sensitive. Apart from enums, a name from a payload is only looked up among the known names (the built-in ones and the registered ones); it never loads a type.
* **Strict:** writing a value whose type (or comparer) has no name throws `JsonException` with the name of the type; reading an unknown name throws.
* Only the exact runtime type of a value matches a name. A subclass of a named type (a `class MyList : List<int>`, an internal class behind a public one) has no name.
* Grammar: a name is a built-in name, a registered name or an enum name, optionally followed by `?` (a nullable value type) and by `[]` (an array, repeatable), or a collection name followed by its element names in `<…>`, separated by `,` without spaces. Inside `<…>`, a name that contains `,`, `<`, `>`, `[`, `]` or `?` (an enum name with its assembly, a registered generic type) is put in square brackets: `list<[MyApp.Orders.OrderStatus, MyApp]>`, `dictionary<string,[MyApp.Orders.OrderStatus, MyApp]?>`.

## Equality after a round trip
A round trip gives back the same .NET types and values, but an `Error` (or a `TemplatedMessage`) whose `Metadata` (or `Parameters`) holds an array or a collection **never equals its round trip**: the core compares the values with `object.Equals`, and two equal arrays or lists are different objects. The elements are equal. Every other value (scalars, enums, core types, registered types with value equality) gives back an equal `Error`.

## Not supported
* **Payloads written by Maple.Result 2.x.** Nothing in the reader is special for them; the general rules apply. A successful 2.x result has `"Error": null` and throws. A failed one has the shape of this format, so it is read, but its `Params` member (now `Parameters`) is an unknown member: skipped by default, so the parameters are lost without an error, unless `UnmappedMemberHandling` is `Disallow`, then the read throws. The category name `Unauthorized` (now `PermissionDenied`) throws; its number `2` is read. To upgrade, finish orchestrations and drain queues first, or map 2.x payloads through a type of your own.
* **A member typed `IOperationResult`**: it is not converted.
* **Values without a name:** `Result` and `Result<T>`, `FrozenSet<T>` and `FrozenDictionary<K,V>`, arrays with more than one dimension, subclasses of the named types, and every type that is not registered.

## Rules decided for this format
The rules below were derived from the decisions of [#12](https://github.com/TomMaple/Maple.Result.Serialization.SystemTextJson/issues/12) and decided one by one by the maintainer on 2026-11-22 (#13). The text above follows them.

| # | Rule | Decision |
| - | ---- | -------- |
| 1 | `Category`, `TypeUri` and `Title` are required (also `TemplateId` and the `Detail` of an error detail); a missing `TypeUri` is not `about:blank`. | confirmed |
| 2 | `null` is read as absent for the members that can be `null`; for a required member it throws. | confirmed |
| 3 | A plain integer is read as `int` only, a plain number with a fraction or exponent as `decimal` only; anything else throws. | changed (was: `int`, else `long`, else `decimal`) |
| 4 | Custom comparers are registered like types; an unregistered custom or culture-specific comparer throws on write; a comparer that is not exposed is read back as the default one; a value comparer of an immutable dictionary that is not the default one throws on write. | confirmed |
| 5 | `byte[]` in base64; `NaN` and the infinities of `float` and `double` as strings. | confirmed |
| 6 | Keys of maps are strings or scalars in their text form; stacks and queues keep their order. | confirmed |
| 7 | An object with a `$type` member is a wrapper in any member order; a malformed wrapper throws, whatever the options say. | changed (was: `$type` first, fixed order) |
| 8 | The `$value` of an enum follows the options, as `Category` does; the reader accepts the number and the names. | changed (was: always the member name) |
| 9 | A runtime type that is not public is treated as its nearest public base type. | deferred: not in this version; only the exact type matches a name, and the frozen collections are not supported |
| 10 | JSON `null` in place of a whole `Result` or `Error` is the `null` reference. | confirmed |

Also decided on 2026-11-22: `StringComparer.Ordinal` is written as `ordinal`; a wrapper of a type that is written plain is read; the test vectors are minified, one line each.
