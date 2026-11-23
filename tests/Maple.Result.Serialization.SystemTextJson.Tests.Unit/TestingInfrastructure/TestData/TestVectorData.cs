// SPDX-License-Identifier: MIT
/*
 * This code is a part of a Maple.Result.Serialization.SystemTextJson library project.
 * https://github.com/TomMaple/Maple.Result.Serialization.SystemTextJson/
 * Copyright (c) Tom Maple
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

using Maple.Results.TestVectors;
using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Collections.ObjectModel;
using System.Collections.Specialized;
using System.IO;
using NonGenericOrderedDictionary = System.Collections.Specialized.OrderedDictionary;

namespace Maple.Results.Serialization.SystemTextJson.Tests.Unit.TestingInfrastructure.TestData;

/// <summary>
///     A valid test vector: the type that the JSON is read as, and a factory of the value that the JSON stands for (a new instance on every call,
///     as some values are mutable collections).
/// </summary>
internal sealed record TestVector(Type Type, Func<object?> Create);

/// <summary>
///     The values of the test vectors in <c>tests/TestVectors</c>, by file name without the extension (docs/format.md).
/// </summary>
/// <remarks>
///     <para>
///         A name of <see cref="Valid" /> has a file in <c>default/</c>, and may have one in <c>camel-case/</c> (the same value, written with
///         camel case, <c>WhenWritingNull</c> and a <c>JsonStringEnumConverter</c>). A name of <see cref="Invalid" /> has a file in
///         <c>invalid/</c>, which must throw a <c>JsonException</c> when read as that type with the default options.
///     </para>
///     <para>The other serializer package copies the files and keeps the same list.</para>
/// </remarks>
internal static class TestVectorData
{
    private const string TagUri = "tag:example.com,2026:orders:not-found";
    private const string GuidText = "0f8fad5b-d9cb-469f-a169-6c0a9e9e7d2c";

    public static IReadOnlyDictionary<string, TestVector> Valid { get; } = new Dictionary<string, TestVector>
    {
        // Result and Result<T>
        ["result-success"] = Vector(() => Result.Success()),
        ["result-failure"] = Vector(() => Result.FromError(MinimalError())),
        ["result-of-order-value"] = Vector(() => Result<Order>.FromValue(new Order(42))),
        ["result-of-order-failure"] = Vector(() => Result<Order>.FromError(MinimalError())),
        ["result-of-string-null"] = Vector(() => Result<string?>.FromValue(null)),
        ["result-of-int-value"] = Vector(() => Result<int>.FromValue(42)),
        ["result-of-nullable-int-null"] = Vector(() => Result<int?>.FromValue(null)),
        ["result-of-nullable-int-value"] = Vector(() => Result<int?>.FromValue(5)),

        // Error, ErrorUri, ErrorDetail, TemplatedMessage
        ["error-minimal"] = Vector(MinimalError),
        ["error-full"] = Vector(FullError),
        ["error-category-validation"] = Vector(() => ErrorBuilder.Validation(ErrorUri.Tag(TagUri), "Order not found.").Build()),
        ["error-metadata-pascal-case-key"] = Vector(() => MinimalErrorBuilder().WithMetadata("RetryAfter", 30).Build()),
        ["error-uri-about-blank"] = Vector(() => ErrorUri.None),
        ["error-uri-relative"] = Vector(() => ErrorUri.Relative("/orders/42")),
        ["error-uri-tag"] = Vector(() => ErrorUri.Tag(TagUri)),
        ["error-uri-urn"] = Vector(() => ErrorUri.Urn("urn:example:orders:not-found")),
        ["error-uri-locator"] = Vector(() => ErrorUri.Locator("https://example.com/errors/not-found")),
        ["error-uri-other"] = Vector(() => ErrorUri.Other("mailto:support@example.com")),
        ["error-detail-minimal"] = Vector(() => new ErrorDetail(null, "Required.")),
        ["error-detail-full"] = Vector(() => new ErrorDetail("/email", "Required.", new TemplatedMessage("signup.email.required"))),
        ["templated-message-without-parameters"] = Vector(() => new TemplatedMessage("orders.notFound")),
        ["templated-message-with-parameters"] = Vector(() => new TemplatedMessage("orders.notFound", ("id", 42), ("name", "x"))),

        // Plain values
        ["value-null"] = Value(() => null),
        ["value-string"] = Value(() => "text"),
        ["value-true"] = Value(() => true),
        ["value-false"] = Value(() => false),
        ["value-int"] = Value(() => 42),
        ["value-int-negative"] = Value(() => -7),
        ["value-decimal"] = Value(() => 5m),
        ["value-decimal-scale"] = Value(() => 5.00m),
        ["value-decimal-fraction"] = Value(() => 0.5m),
        ["value-array-empty"] = Value(() => Array.Empty<object?>()),
        ["value-array-int"] = Value(() => new[] { 1, 2, 3 }),
        ["value-array-string-with-null"] = Value(() => new[] { "a", null }),
        ["value-array-decimal"] = Value(() => new[] { 1.5m, 2.0m }),
        ["value-array-bool"] = Value(() => new[] { true, false }),
        ["value-array-nested-int"] = Value(() => new[] { new[] { 1, 2 }, new[] { 3 } }),
        ["value-array-first-null"] = Value(() => new object?[] { null, 1, "a" }),
        ["value-array-of-dictionaries"] = Value(() => new[] { new Dictionary<string, int> { ["a"] = 1 } }),
        ["value-dictionary-empty"] = Value(() => new Dictionary<string, object?>()),
        ["value-dictionary-int"] = Value(() => new Dictionary<string, int> { ["a"] = 1, ["b"] = 2 }),
        ["value-dictionary-first-null"] = Value(() => new Dictionary<string, object?> { ["a"] = null, ["b"] = 1, ["c"] = "x" }),
        ["value-dictionary-nested"] = Value(() => new Dictionary<string, Dictionary<string, int>> { ["a"] = new() { ["x"] = 1 } }),
        ["value-dictionary-of-arrays"] = Value(() => new Dictionary<string, int[]> { ["a"] = [1, 2] }),

        // Scalar types
        ["value-char"] = Value(() => 'a'),
        ["value-sbyte"] = Value(() => (sbyte)-5),
        ["value-byte"] = Value(() => (byte)200),
        ["value-short"] = Value(() => (short)-300),
        ["value-ushort"] = Value(() => (ushort)60000),
        ["value-uint"] = Value(() => 4000000000u),
        ["value-long"] = Value(() => 5000000000L),
        ["value-ulong"] = Value(() => ulong.MaxValue),
        ["value-float"] = Value(() => 0.5f),
        ["value-double"] = Value(() => 0.1d),
        ["value-double-large"] = Value(() => 1e30d),
        ["value-double-nan"] = Value(() => double.NaN),
        ["value-double-positive-infinity"] = Value(() => double.PositiveInfinity),
        ["value-double-negative-infinity"] = Value(() => double.NegativeInfinity),
        ["value-guid"] = Value(() => Guid.Parse(GuidText)),
        ["value-uri-absolute"] = Value(() => new Uri("https://example.com/a?b=1")),
        ["value-uri-relative"] = Value(() => new Uri("/orders/42", UriKind.Relative)),
        ["value-date-time-offset"] = Value(() => new DateTimeOffset(2026, 12, 1, 8, 30, 0, TimeSpan.FromHours(1))),
        ["value-date-time-utc"] = Value(() => new DateTime(2026, 12, 1, 8, 30, 0, DateTimeKind.Utc)),
        ["value-date-time-unspecified"] = Value(() => new DateTime(2026, 12, 1, 8, 30, 0, DateTimeKind.Unspecified)),
        ["value-date-only"] = Value(() => new DateOnly(2026, 12, 1)),
        ["value-time-only"] = Value(() => new TimeOnly(8, 30)),
        ["value-time-span"] = Value(() => new TimeSpan(1, 2, 3, 4, 500)),
        ["value-time-span-negative"] = Value(() => TimeSpan.FromSeconds(-1)),
        ["value-byte-array"] = Value(() => new byte[] { 1, 2, 3 }),

        // Core types as values
        ["value-error"] = Value(MinimalError),
        ["value-error-uri"] = Value(() => ErrorUri.Relative("/orders/42")),
        ["value-error-detail"] = Value(() => new ErrorDetail("/email", "Required.")),
        ["value-templated-message"] = Value(() => new TemplatedMessage("t")),
        ["value-error-category"] = Value(() => ErrorCategory.NotFound),

        // Wrapped arrays and dictionaries
        ["value-long-array"] = Value(() => new[] { 1L, 2L }),
        ["value-string-array-empty"] = Value(() => Array.Empty<string>()),
        ["value-object-array-mixed"] = Value(() => new object?[] { 1, "a", 5L }),
        ["value-nullable-int-array"] = Value(() => new int?[] { 1, null }),
        ["value-jagged-long-array"] = Value(() => new[] { new[] { 1L }, new[] { 2L, 3L } }),
        ["value-guid-array"] = Value(() => new[] { Guid.Parse(GuidText) }),
        ["value-dictionary-dollar-key"] = Value(() => new Dictionary<string, int> { ["$id"] = 1 }),
        ["value-dictionary-object-mixed"] = Value(() => new Dictionary<string, object?> { ["a"] = 1, ["b"] = "x" }),

        // Generic sequences
        ["collection-list"] = Value(() => new List<int> { 1, 2 }),
        ["collection-hash-set"] = Value(() => new HashSet<int> { 1, 2 }),
        ["collection-sorted-set"] = Value(() => new SortedSet<int> { 1, 2 }),
        ["collection-linked-list"] = Value(() => new LinkedList<int>([1, 2])),
        ["collection-queue"] = Value(() => new Queue<int>([1, 2])),
        ["collection-stack"] = Value(() => new Stack<int>([1, 2])),
        ["collection-collection"] = Value(() => new Collection<int> { 1, 2 }),
        ["collection-read-only-collection"] = Value(() => new ReadOnlyCollection<int>([1, 2])),
        ["collection-observable-collection"] = Value(() => new ObservableCollection<int> { 1, 2 }),
        ["collection-immutable-array"] = Value(() => ImmutableArray.Create(1, 2)),
        ["collection-immutable-list"] = Value(() => ImmutableList.Create(1, 2)),
        ["collection-immutable-hash-set"] = Value(() => ImmutableHashSet.Create(1, 2)),
        ["collection-immutable-sorted-set"] = Value(() => ImmutableSortedSet.Create(1, 2)),
        ["collection-immutable-queue"] = Value(() => ImmutableQueue.Create(1, 2)),
        ["collection-immutable-stack"] = Value(() => ImmutableStack.Create(1, 2)),
        ["collection-concurrent-queue"] = Value(() => new ConcurrentQueue<int>([1, 2])),
        ["collection-concurrent-stack"] = Value(() => new ConcurrentStack<int>([1, 2])),
        ["collection-concurrent-bag"] = Value(() => new ConcurrentBag<int> { 1 }),

        // Generic maps
        ["collection-dictionary"] = Value(() => new Dictionary<int, string> { [1] = "a", [2] = "b" }),
        ["collection-sorted-dictionary"] = Value(() => new SortedDictionary<string, int> { ["a"] = 1, ["b"] = 2 }),
        ["collection-sorted-list"] = Value(() => new SortedList<string, int> { ["a"] = 1, ["b"] = 2 }),
        ["collection-ordered-dictionary"] = Value(() => new OrderedDictionary<string, int> { ["b"] = 2, ["a"] = 1 }),
        ["collection-read-only-dictionary"] = Value(() => new ReadOnlyDictionary<string, int>(new Dictionary<string, int> { ["a"] = 1 })),
        ["collection-immutable-dictionary"] = Value(() => ImmutableDictionary<string, int>.Empty.Add("a", 1)),
        ["collection-immutable-sorted-dictionary"] = Value(() => ImmutableSortedDictionary<string, int>.Empty.Add("a", 1).Add("b", 2)),
        ["collection-concurrent-dictionary"] = Value(() => new ConcurrentDictionary<string, int> { ["a"] = 1 }),

        // Non-generic collections
        ["collection-array-list"] = Value(() => new ArrayList { 1, "a", 5L }),
        ["collection-queue-non-generic"] = Value(() => new Queue(new object[] { 1, "a" })),
        ["collection-stack-non-generic"] = Value(() => new Stack(new object[] { 1, "a" })),
        ["collection-string-collection"] = Value(() => new StringCollection { "a", null }),
        ["collection-hashtable"] = Value(() => new Hashtable { ["a"] = 1 }),
        ["collection-sorted-list-non-generic"] = Value(() => new SortedList { ["a"] = 1, ["b"] = "x" }),
        ["collection-string-dictionary"] = Value(() => new StringDictionary { ["a"] = "x" }),
        ["collection-name-value-collection"] = Value(() => new NameValueCollection { { "a", "1" }, { "a", "2" }, { "b", "3" } }),
        ["collection-list-dictionary"] = Value(() => new ListDictionary { ["a"] = 1, ["b"] = "x" }),
        ["collection-hybrid-dictionary"] = Value(() => new HybridDictionary { ["a"] = 1 }),
        ["collection-ordered-dictionary-non-generic"] = Value(() => new NonGenericOrderedDictionary { ["b"] = 2, ["a"] = "x" }),

        // Composed names and keys
        ["collection-list-of-lists"] = Value(() => new List<List<int>> { new() { 1 }, new() { 2, 3 } }),
        ["collection-list-of-nullable-int"] = Value(() => new List<int?> { 1, null }),
        ["collection-dictionary-guid-keys"] = Value(() => new Dictionary<Guid, int> { [Guid.Parse(GuidText)] = 1 }),
        ["collection-dictionary-of-objects"] = Value(() => new SortedDictionary<string, object?> { ["a"] = 5L, ["b"] = null }),

        // Comparers
        ["comparer-hash-set-ordinal-ignore-case"] = Value(() => new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "a" }),
        ["comparer-dictionary-ordinal"] = Value(() => new Dictionary<string, int>(StringComparer.Ordinal) { ["a"] = 1 }),
        ["comparer-sorted-set-invariant-culture"] = Value(() => new SortedSet<string>(StringComparer.InvariantCulture) { "a", "B" }),
        ["comparer-immutable-hash-set-invariant-culture-ignore-case"] =
            Value(() => ImmutableHashSet.Create(StringComparer.InvariantCultureIgnoreCase, "a")),
        ["comparer-registered"] = Value(() => new SortedSet<string>(ReverseOrdinalComparer.Instance) { "a", "b" }),

        // Enums
        ["enum-day-of-week"] = Value(() => DayOfWeek.Monday),
        ["enum-flags"] = Value(() => FileAttributes.ReadOnly | FileAttributes.Hidden),
        ["enum-unnamed-value"] = Value(() => (DayOfWeek)99),
        ["enum-in-list"] = Value(() => new List<DayOfWeek> { DayOfWeek.Monday, DayOfWeek.Friday }),

        // Registered types
        ["registered-type"] = Value(() => new CustomerRef(7)),
        ["registered-type-in-list"] = Value(() => new List<CustomerRef> { new(7) })
    };

    public static IReadOnlyDictionary<string, Type> Invalid { get; } = new Dictionary<string, Type>
    {
        // Result and Result<T>
        ["result-of-int-without-value-or-error"] = typeof(Result<int>),
        ["result-of-int-with-value-and-error"] = typeof(Result<int>),
        ["result-with-value"] = typeof(Result),
        ["result-error-null"] = typeof(Result),
        ["result-unknown-member"] = typeof(Result),
        ["result-2x-success"] = typeof(Result),

        // Error
        ["error-missing-category"] = typeof(Error),
        ["error-null-category"] = typeof(Error),
        ["error-undefined-category"] = typeof(Error),
        ["error-unknown-category-name"] = typeof(Error),
        ["error-missing-type-uri"] = typeof(Error),
        ["error-null-type-uri"] = typeof(Error),
        ["error-invalid-type-uri"] = typeof(Error),
        ["error-missing-title"] = typeof(Error),
        ["error-blank-title"] = typeof(Error),
        ["error-instance-uri-about-blank"] = typeof(Error),
        ["error-invalid-property-pointer"] = typeof(Error),
        ["error-detail-missing-detail"] = typeof(Error),
        ["error-reserved-metadata-key"] = typeof(Error),
        ["error-metadata-keys-differ-in-case"] = typeof(Error),

        // TemplatedMessage
        ["templated-message-missing-template-id"] = typeof(TemplatedMessage),
        ["templated-message-blank-template-id"] = typeof(TemplatedMessage),
        ["templated-message-parameter-names-differ-in-case"] = typeof(TemplatedMessage),

        // Plain values
        ["value-integer-out-of-int-range"] = typeof(TemplatedMessage),
        ["value-number-out-of-decimal-range"] = typeof(TemplatedMessage),
        ["value-array-int-then-string"] = typeof(TemplatedMessage),
        ["value-array-int-then-decimal"] = typeof(TemplatedMessage),
        ["value-array-int-then-null"] = typeof(TemplatedMessage),
        ["value-dictionary-int-then-string"] = typeof(TemplatedMessage),

        // Wrappers
        ["wrapper-missing-value"] = typeof(TemplatedMessage),
        ["wrapper-unknown-member"] = typeof(TemplatedMessage),
        ["wrapper-repeated-member"] = typeof(TemplatedMessage),
        ["wrapper-unknown-type"] = typeof(TemplatedMessage),
        ["wrapper-type-in-other-case"] = typeof(TemplatedMessage),
        ["wrapper-type-not-a-string"] = typeof(TemplatedMessage),
        ["wrapper-value-not-valid"] = typeof(TemplatedMessage),
        ["wrapper-value-out-of-range"] = typeof(TemplatedMessage),
        ["wrapper-char-with-two-characters"] = typeof(TemplatedMessage),
        ["wrapper-guid-not-in-format-d"] = typeof(TemplatedMessage),
        ["wrapper-date-time-offset-not-in-format-o"] = typeof(TemplatedMessage),
        ["wrapper-typed-array-with-wrong-element"] = typeof(TemplatedMessage),
        ["wrapper-unknown-comparer"] = typeof(TemplatedMessage),
        ["wrapper-comparer-on-list"] = typeof(TemplatedMessage),
        ["wrapper-enum-name-not-an-enum"] = typeof(TemplatedMessage),
        ["wrapper-enum-unknown-member"] = typeof(TemplatedMessage),
        ["wrapper-enum-unknown-type"] = typeof(TemplatedMessage),
        ["wrapper-collection-with-unknown-element-type"] = typeof(TemplatedMessage)
    };

    private static ErrorBuilder MinimalErrorBuilder()
    {
        return ErrorBuilder.NotFound(ErrorUri.Tag(TagUri), "Order not found.");
    }

    private static Error MinimalError()
    {
        return MinimalErrorBuilder().Build();
    }

    private static Error FullError()
    {
        return MinimalErrorBuilder()
            .WithDetail("Order 42 does not exist.")
            .WithInstanceUri(ErrorUri.Relative("/orders/42"))
            .WithDetailTemplated("orders.notFound", ("id", 42))
            .AddErrorDetail("/orderId", "Unknown order.")
            .WithMetadata(("retryable", false), ("limit", 100L))
            .Build();
    }

    private static TestVector Vector<T>(Func<T> create)
    {
        return new TestVector(typeof(T), () => create());
    }

    // A value vector: the value is the only parameter, "value", of a templated message.
    private static TestVector Value(Func<object?> create)
    {
        return new TestVector(typeof(TemplatedMessage), () => new TemplatedMessage("value", ("value", create())));
    }
}
