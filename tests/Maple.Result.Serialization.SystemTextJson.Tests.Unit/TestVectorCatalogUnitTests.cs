// SPDX-License-Identifier: MIT
/*
 * This code is a part of a Maple.Result.Serialization.SystemTextJson library project.
 * https://github.com/TomMaple/Maple.Result.Serialization.SystemTextJson/
 * Copyright (c) Tom Maple
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

using Maple.Results.Serialization.SystemTextJson.Tests.Unit.TestingInfrastructure.TestData;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace Maple.Results.Serialization.SystemTextJson.Tests.Unit;

// The files in tests/TestVectors and the entries of TestVectorData must match: a file without an entry, or an entry without a file, fails.
public class TestVectorCatalogUnitTests
{
    public static TheoryData<string> ValidNames => new(TestVectorData.Valid.Keys.Order(StringComparer.Ordinal));

    [Fact]
    public void DefaultFiles_EveryFile_HasValidEntry()
    {
        // Act
        var result = FileNames("default").Except(TestVectorData.Valid.Keys);

        // Assert
        result.ShouldBeEmpty();
    }

    [Fact]
    public void ValidEntries_EveryEntry_HasDefaultFile()
    {
        // Act
        var result = TestVectorData.Valid.Keys.Except(FileNames("default"));

        // Assert
        result.ShouldBeEmpty();
    }

    [Fact]
    public void CamelCaseFiles_EveryFile_HasValidEntry()
    {
        // Act
        var result = FileNames("camel-case").Except(TestVectorData.Valid.Keys);

        // Assert
        result.ShouldBeEmpty();
    }

    [Fact]
    public void InvalidFiles_EveryFile_HasInvalidEntry()
    {
        // Act
        var result = FileNames("invalid").Except(TestVectorData.Invalid.Keys);

        // Assert
        result.ShouldBeEmpty();
    }

    [Fact]
    public void InvalidEntries_EveryEntry_HasInvalidFile()
    {
        // Act
        var result = TestVectorData.Invalid.Keys.Except(FileNames("invalid"));

        // Assert
        result.ShouldBeEmpty();
    }

    [Fact]
    public void InvalidEntries_NoEntry_IsValidEntry()
    {
        // Act
        var result = TestVectorData.Invalid.Keys.Intersect(TestVectorData.Valid.Keys);

        // Assert
        result.ShouldBeEmpty();
    }

    // The core validates every value, so a value that the core rejects fails here, not in the converter tests.
    [Theory]
    [MemberData(nameof(ValidNames))]
    public void ValidEntry_Create_ReturnsValueOfItsType(string name)
    {
        // Arrange
        var vector = TestVectorData.Valid[name];

        // Act
        var result = vector.Create();

        // Assert
        result.ShouldBeAssignableTo(vector.Type);
    }

    private static IEnumerable<string> FileNames(string set)
    {
        return Directory.EnumerateFiles(Path.Combine(TestVectorsDirectory(), set), "*.json")
            .Select(Path.GetFileNameWithoutExtension)
            .OfType<string>();
    }

    private static string TestVectorsDirectory()
    {
        for (var directory = new DirectoryInfo(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            var candidate = Path.Combine(directory.FullName, "tests", "TestVectors");
            if (Directory.Exists(candidate))
                return candidate;
        }

        throw new DirectoryNotFoundException($"No tests/TestVectors folder above '{AppContext.BaseDirectory}'.");
    }
}
