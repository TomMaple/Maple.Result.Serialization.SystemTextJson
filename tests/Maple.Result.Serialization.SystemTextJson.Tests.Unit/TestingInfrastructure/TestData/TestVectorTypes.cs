// SPDX-License-Identifier: MIT
/*
 * This code is a part of a Maple.Result.Serialization.SystemTextJson library project.
 * https://github.com/TomMaple/Maple.Result.Serialization.SystemTextJson/
 * Copyright (c) Tom Maple
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

using System;
using System.Collections.Generic;

// The types that the test vectors name. The namespace is part of their names in the vectors
// ("Maple.Results.TestVectors.CustomerRef"), so it is the same in every package that reads the vectors,
// and it does not follow the folder.
namespace Maple.Results.TestVectors;

/// <summary>The value of a successful <c>Result&lt;Order&gt;</c> in the vectors.</summary>
public sealed record Order(int Id);

/// <summary>A registered type in the vectors: <c>"$type":"Maple.Results.TestVectors.CustomerRef"</c>.</summary>
public sealed record CustomerRef(int Id);

/// <summary>A registered comparer in the vectors: the reverse of the ordinal order of strings.</summary>
public sealed class ReverseOrdinalComparer : IComparer<string>, IEqualityComparer<string>
{
    public static ReverseOrdinalComparer Instance { get; } = new();

    public int Compare(string? x, string? y)
    {
        return string.CompareOrdinal(y, x);
    }

    public bool Equals(string? x, string? y)
    {
        return string.Equals(x, y, StringComparison.Ordinal);
    }

    public int GetHashCode(string obj)
    {
        return StringComparer.Ordinal.GetHashCode(obj);
    }
}
