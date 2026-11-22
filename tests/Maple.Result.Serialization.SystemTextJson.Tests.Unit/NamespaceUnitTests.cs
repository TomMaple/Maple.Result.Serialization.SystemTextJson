// SPDX-License-Identifier: MIT
/*
 * This code is a part of a Maple.Result.Serialization.SystemTextJson library project.
 * https://github.com/TomMaple/Maple.Result.Serialization.SystemTextJson/
 * Copyright (c) Tom Maple
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

namespace Maple.Results.Serialization.SystemTextJson.Tests.Unit;

// The package ID and the assembly name are Maple.Result.Serialization.SystemTextJson; the namespaces are Maple.Results.*,
// as in the core (core #178).
public class NamespaceUnitTests
{
    [Fact]
    public void Namespace_LibraryType_IsMapleResultsSerializationSystemTextJson()
    {
        // Act
        var result = typeof(AssemblyMarker).Namespace;

        // Assert
        result.ShouldBe("Maple.Results.Serialization.SystemTextJson");
    }

    [Fact]
    public void AssemblyName_Library_IsPackageId()
    {
        // Act
        var result = typeof(AssemblyMarker).Assembly.GetName().Name;

        // Assert
        result.ShouldBe("Maple.Result.Serialization.SystemTextJson");
    }
}
