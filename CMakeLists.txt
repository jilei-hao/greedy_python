CMAKE_MINIMUM_REQUIRED(VERSION 3.15)
PROJECT(PICSL_Greedy)

# Enable languages
ENABLE_LANGUAGE(CXX)

# Specify the C++ standard
SET(CMAKE_CXX_STANDARD 17)
SET(CMAKE_CXX_STANDARD_REQUIRED ON)

# Avoid -fPIC errors
SET(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Option, whether to fetch external dependencies or to find locally
set(FETCH_DEPENDENCIES OFF CACHE BOOL "Fetch dependencies (ITK, VTK and Greedy)?")
set(DEPENDENCIES_ONLY OFF CACHE BOOL "Only build dependencies, skip main build")

# If requested, fetch the dependencies
IF(FETCH_DEPENDENCIES)

    # Dependency: ITK
    include(FetchContent)
    set(Module_MorphologicalContourInterpolation ON CACHE BOOL "" FORCE)
    set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
    FetchContent_Declare(
        ITK
        GIT_REPOSITORY https://github.com/InsightSoftwareConsortium/ITK.git
        GIT_TAG        v5.4.0
    )
    FetchContent_MakeAvailable(ITK)
    SET(ITK_DIR ${itk_BINARY_DIR})
    FIND_PACKAGE(ITK CONFIG REQUIRED)
    INCLUDE(${ITK_USE_FILE})

    # ITK seems to mess things up by setting these variables
    UNSET(CMAKE_ARCHIVE_OUTPUT_DIRECTORY)
    UNSET(CMAKE_RUNTIME_OUTPUT_DIRECTORY)
    UNSET(CMAKE_LIBRARY_OUTPUT_DIRECTORY)

    # Dependency: VTK
    set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
    set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
    set(VTK_REQUIRED_OBJCXX_FLAGS "" CACHE STRING "" FORCE)
    set(VTK_MODULE_ENABLE_VTK_IOHDF5 OFF CACHE BOOL "" FORCE)
    FetchContent_Declare(
        VTK
        GIT_REPOSITORY https://github.com/Kitware/VTK.git
        GIT_TAG        v9.3.1
    )
    FetchContent_MakeAvailable(VTK)
    SET(VTK_DIR ${vtk_BINARY_DIR})
    FIND_PACKAGE(VTK REQUIRED COMPONENTS CommonCore IOCore IOLegacy IOPLY IOGeometry FiltersModeling)
    
    # Dependency: Greedy
    SET(GREEDY_BUILD_LDDMM ON CACHE BOOL "" FORCE)
    FetchContent_Declare(
        Greedy
        GIT_REPOSITORY https://github.com/pyushkevich/greedy.git
        GIT_TAG        master
    )
    FetchContent_MakeAvailable(Greedy)
    INCLUDE_DIRECTORIES(${greedy_SOURCE_DIR}/src)
    INCLUDE_DIRECTORIES(${greedy_SOURCE_DIR}/src/propagation)
    
ELSE()

    # Find ITK and C3D
    MESSAGE(STATUS "CMAKE_PREFIX_PATH=${CMAKE_PREFIX_PATH}")
    FIND_PACKAGE(ITK REQUIRED)
    INCLUDE(${ITK_USE_FILE})

    FIND_PACKAGE(VTK REQUIRED COMPONENTS CommonCore IOCore IOLegacy IOPLY IOGeometry FiltersModeling)

    FIND_PACKAGE(Greedy REQUIRED)

    # Compatibility shim: Greedy built against an ITK with shared HDF5 may reference
    # hdf5_cpp-shared / hdf5-shared / hdf5_hl-shared targets that no longer exist when
    # linking against an ITK that ships static-only HDF5.  Create IMPORTED STATIC
    # targets with the same names so the linker resolves them correctly.
    FOREACH(_hdf5_variant "" "_cpp" "_hl" "_hl_cpp")
        SET(_shared_tgt "hdf5${_hdf5_variant}-shared")
        SET(_static_tgt "hdf5${_hdf5_variant}-static")
        IF(TARGET ${_static_tgt} AND NOT TARGET ${_shared_tgt})
            ADD_LIBRARY(${_shared_tgt} IMPORTED STATIC GLOBAL)
            GET_TARGET_PROPERTY(_loc ${_static_tgt} IMPORTED_LOCATION_RELEASE)
            IF(NOT _loc)
                GET_TARGET_PROPERTY(_loc ${_static_tgt} IMPORTED_LOCATION)
            ENDIF()
            SET_TARGET_PROPERTIES(${_shared_tgt} PROPERTIES IMPORTED_LOCATION "${_loc}")
        ENDIF()
    ENDFOREACH()

ENDIF()

# Set up VTK
vtk_module_autoinit(
  TARGETS greedyapi lmshootapi
  MODULES ${VTK_LIBRARIES})

# Python bindings
IF(NOT DEPENDENCIES_ONLY)
    SET(PYBIND11_FINDPYTHON ON)
    ADD_SUBDIRECTORY(external/pybind11)
    INCLUDE_DIRECTORIES(external/pybind11)
    pybind11_add_module(_picsl_greedy src/GreedyPythonBindings.cxx)
    TARGET_INCLUDE_DIRECTORIES(_picsl_greedy PRIVATE ${Greedy_INCLUDE_DIRS} ${Greedy_INCLUDE_DIRS}/propagation)
    TARGET_LINK_LIBRARIES(_picsl_greedy PUBLIC ${ITK_LIBRARIES} ${VTK_LIBRARIES} greedyapi lmshootapi multichunkgreedyapi propagationapi)
    install(TARGETS _picsl_greedy DESTINATION picsl_greedy)
ENDIF()