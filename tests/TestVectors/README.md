# Test vectors

JSON payloads of the [format](../../docs/format.md), shared by `Maple.Result.Serialization.SystemTextJson` and `Maple.Result.Serialization.NewtonsoftJson`: both packages read and write the same files. This folder is the source; the other package copies it and checks the copy in its CI.

## Sets
| Folder | Options | Use |
| ------ | ------- | --- |
| `default/` | the default options: no naming policy, `null` members written, enums as numbers | every valid vector |
| `camel-case/` | `PropertyNamingPolicy = JsonNamingPolicy.CamelCase`, `DefaultIgnoreCondition = WhenWritingNull`, a `JsonStringEnumConverter` (without a naming policy) | the vectors whose JSON depends on these options |
| `invalid/` | the default options | payloads that must throw `JsonException` when they are read |

All other options keep their defaults, also `AllowDuplicateProperties`, `UnmappedMemberHandling` and `RespectNullableAnnotations`.

## Files
* One JSON value per file, minified on one line, followed by a newline. The newline is not part of the value.
* The name of a file is the name of the vector. In the test project, `TestingInfrastructure/TestData/TestVectorData.cs` has an entry for every name: for a valid vector, the type that the JSON is read as and the value that it stands for; for an invalid one, the type that the read targets. A test fails when a file has no entry, or an entry has no file.
* A file in `camel-case/` has the same name as the file in `default/` with the same value.
* `value-*`, `collection-*`, `comparer-*`, `enum-*` and `registered-*` vectors are a `TemplatedMessage` whose only parameter, `value`, holds the value: `{"TemplateId":"value","Parameters":{"value":…}}`.
* The names in the invalid set say which rule the payload breaks.

## Types
The vectors that need types of their own use types that every package can declare with the same names:
* `Maple.Results.TestVectors.Order` (`record Order(int Id)`), the value of `Result<Order>`;
* `Maple.Results.TestVectors.CustomerRef` (`record CustomerRef(int Id)`), registered with `ValueTypes.Add<CustomerRef>()`;
* `Maple.Results.TestVectors.ReverseOrdinalComparer` (the reverse of the ordinal order of strings), registered with `ValueComparers.Add(…)`;
* the enums `System.DayOfWeek` and `System.IO.FileAttributes` (flags), resolved by name from `System.Private.CoreLib`.

## How a package checks them
* **Valid vectors, both directions, per set:** the file is read as its type with the options of the set, and the result equals the value of the entry (for an array or a collection, its elements: see *Equality after a round trip* in the format); then the value is written with the options of the set, and the output equals the file, compared token by token: the same members in the same order, the same strings after unescaping, and the same text for every number. Comparing tokens instead of bytes keeps the vectors independent of the encoder: the default encoder of *System.Text.Json* escapes `+` and `<`, *Newtonsoft.Json* does not. The strings of the vectors contain no escape sequences.
* **Invalid vectors:** reading the file as its type with the default options throws `JsonException`.

Behaviour that a pair of files cannot show (a wrapper of a type that is written plain, which reads but is written back plain; the effect of each option; payloads of Maple.Result 2.x, which read with a loss) is tested by unit tests, not by vectors.
