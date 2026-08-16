#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace
{
const double Pi = 3.14159265358979323846;
const double RayEpsilon = 1.0e-4;

struct Vec3
{
    double x, y, z;

    Vec3() : x(0.0), y(0.0), z(0.0) {}
    explicit Vec3(double v) : x(v), y(v), z(v) {}
    Vec3(double ax, double ay, double az) : x(ax), y(ay), z(az) {}

    double& operator[](int i) { return i == 0 ? x : (i == 1 ? y : z); }
    double operator[](int i) const { return i == 0 ? x : (i == 1 ? y : z); }
};

Vec3 operator+(const Vec3& a, const Vec3& b) { return Vec3(a.x + b.x, a.y + b.y, a.z + b.z); }
Vec3 operator-(const Vec3& a, const Vec3& b) { return Vec3(a.x - b.x, a.y - b.y, a.z - b.z); }
Vec3 operator-(const Vec3& v) { return Vec3(-v.x, -v.y, -v.z); }
Vec3 operator*(const Vec3& a, const Vec3& b) { return Vec3(a.x * b.x, a.y * b.y, a.z * b.z); }
Vec3 operator*(const Vec3& v, double s) { return Vec3(v.x * s, v.y * s, v.z * s); }
Vec3 operator*(double s, const Vec3& v) { return v * s; }
Vec3 operator/(const Vec3& v, double s) { return Vec3(v.x / s, v.y / s, v.z / s); }
Vec3& operator+=(Vec3& a, const Vec3& b) { a = a + b; return a; }
Vec3& operator*=(Vec3& a, const Vec3& b) { a = a * b; return a; }
Vec3& operator/=(Vec3& a, double s) { a = a / s; return a; }

double dot(const Vec3& a, const Vec3& b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
Vec3 cross(const Vec3& a, const Vec3& b)
{
    return Vec3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
}
double length(const Vec3& v) { return std::sqrt(dot(v, v)); }
Vec3 normalize(const Vec3& v)
{
    const double len = length(v);
    return len > 0.0 ? v / len : Vec3(0.0);
}
Vec3 maxVec(const Vec3& v, double floorValue)
{
    return Vec3(std::max(v.x, floorValue), std::max(v.y, floorValue), std::max(v.z, floorValue));
}
Vec3 maxVec(const Vec3& a, const Vec3& b)
{
    return Vec3(std::max(a.x, b.x), std::max(a.y, b.y), std::max(a.z, b.z));
}

struct Ray
{
    Vec3 origin;
    Vec3 direction;
};

struct Material
{
    Vec3 albedo;
    double metallic;
    double roughness;
    double ior;
};

struct Box
{
    Vec3 minimum;
    Vec3 maximum;
    Material material;
};

struct Hit
{
    bool found;
    double distance;
    Vec3 position;
    Vec3 normal;
    Material material;

    Hit() : found(false), distance(std::numeric_limits<double>::infinity()) {}
};

struct Light
{
    Vec3 position;
    Vec3 intensity;
};

struct Camera
{
    Vec3 position;
    Vec3 target;
    double verticalFovDegrees;
};

struct Snapshot
{
    std::string name;
    Camera camera;
    Light light;
};

struct Options
{
    int width;
    int height;
    int samplesPerPixel;
    int maxBounces;
    int threads;
    std::uint64_t seed;
    std::string outputDirectory;
    std::string onlySnapshot;
    bool customSnapshot;
    bool hasCameraPosition;
    bool hasCameraYaw;
    bool hasCameraPitch;
    bool hasCameraFov;
    bool hasLightPosition;
    Vec3 cameraPosition;
    double cameraYawDegrees;
    double cameraPitchDegrees;
    double cameraFovDegrees;
    Vec3 lightPosition;
    Vec3 lightIntensity;
    double materialMetallic;
    double materialRoughness;
    double materialIor;
    double materialAo;

    Options() :
        width(800), height(600), samplesPerPixel(4096), maxBounces(2),
        threads(static_cast<int>(std::max(1u, std::thread::hardware_concurrency()))),
        seed(20260812u), outputDirectory("offline-results"), onlySnapshot(),
        customSnapshot(false), hasCameraPosition(false), hasCameraYaw(false),
        hasCameraPitch(false), hasCameraFov(false), hasLightPosition(false),
        cameraPosition(), cameraYawDegrees(0.0), cameraPitchDegrees(0.0),
        cameraFovDegrees(45.0), lightPosition(), lightIntensity(150.0),
        materialMetallic(0.0), materialRoughness(1.0), materialIor(1.5), materialAo(1.0) {}
};

struct Rng
{
    std::uint64_t state;
    std::uint64_t sampleIndex;
    int dimension;

    Rng(std::uint64_t seed, std::uint64_t index) :
        state(seed ? seed : 1u), sampleIndex(index + 1u), dimension(0) {}

    static double radicalInverse(std::uint64_t value, unsigned int base)
    {
        const double inverseBase = 1.0 / static_cast<double>(base);
        double inversePower = inverseBase;
        double result = 0.0;
        while (value != 0u)
        {
            result += static_cast<double>(value % base) * inversePower;
            value /= base;
            inversePower *= inverseBase;
        }
        return result;
    }

    double uniform()
    {
        static const unsigned int bases[2] = { 2u, 3u };
        const int currentDimension = dimension++;
        const unsigned int base = bases[currentDimension % 2];

        std::uint64_t bits = state + UINT64_C(0x9e3779b97f4a7c15)
            * static_cast<std::uint64_t>(currentDimension + 1);
        bits = (bits ^ (bits >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
        bits = (bits ^ (bits >> 27)) * UINT64_C(0x94d049bb133111eb);
        bits ^= bits >> 31;
        const double shift = static_cast<double>(bits >> 11) * (1.0 / 9007199254740992.0);
        const double value = radicalInverse(sampleIndex, base) + shift;
        return value - std::floor(value);
    }
};

std::uint64_t mixBits(std::uint64_t value)
{
    value += UINT64_C(0x9e3779b97f4a7c15);
    value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

std::uint64_t hashString(const std::string& value)
{
    std::uint64_t hash = UINT64_C(1469598103934665603);
    for (std::size_t i = 0; i < value.size(); ++i)
    {
        hash ^= static_cast<unsigned char>(value[i]);
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}

class Scene
{
public:
    Scene(double metallic, double roughness, double ior)
    {
        const Material gray = { Vec3(0.5, 0.5, 0.5), metallic, roughness, ior };
        for (int side = -1; side <= 1; side += 2)
        {
            for (int zIndex = -1; zIndex <= 1; ++zIndex)
            {
                const double x = 7.0 * static_cast<double>(side);
                const double z = 6.0 * static_cast<double>(zIndex);
                Box box;
                box.minimum = Vec3(x - 1.0, 0.0, z - 1.0);
                box.maximum = Vec3(x + 1.0, 2.0, z + 1.0);
                box.material = gray;
                boxes_.push_back(box);
            }
        }
    }

    bool intersect(const Ray& ray, Hit& closest, double maximumDistance = std::numeric_limits<double>::infinity()) const
    {
        intersectRoom(ray, maximumDistance, closest);
        for (std::size_t i = 0; i < boxes_.size(); ++i)
            intersectBox(ray, boxes_[i], maximumDistance, closest);
        return closest.found;
    }

    bool occluded(const Vec3& point, const Vec3& normal, const Vec3& lightPosition) const
    {
        const Vec3 toLight = lightPosition - point;
        const double distanceToLight = length(toLight);
        Ray shadowRay = { point + normal * RayEpsilon, toLight / distanceToLight };
        Hit hit;
        return intersect(shadowRay, hit, distanceToLight - 2.0 * RayEpsilon);
    }

private:
    std::vector<Box> boxes_;

    static Material roomMaterial(int axis, int side, double metallic, double roughness, double ior)
    {
        // 与 main.cpp 的六个 wall material 对应：前红、地面灰、后绿、顶灰、右蓝、左灰。
        if (axis == 2 && side > 0)
            return Material{ Vec3(0.5, 0.0, 0.0), metallic, roughness, ior };
        if (axis == 2 && side < 0)
            return Material{ Vec3(0.0, 0.5, 0.0), metallic, roughness, ior };
        if (axis == 0 && side > 0)
            return Material{ Vec3(0.0, 0.0, 0.5), metallic, roughness, ior };
        return Material{ Vec3(0.5, 0.5, 0.5), metallic, roughness, ior };
    }

    void intersectRoom(const Ray& ray, double maximumDistance, Hit& closest) const
    {
        const double boundsMin[3] = { -9.9, 0.1, -9.9 };
        const double boundsMax[3] = { 9.9, 9.9, 9.9 };

        for (int axis = 0; axis < 3; ++axis)
        {
            if (std::fabs(ray.direction[axis]) < 1.0e-12)
                continue;
            for (int side = -1; side <= 1; side += 2)
            {
                const double plane = side < 0 ? boundsMin[axis] : boundsMax[axis];
                const double t = (plane - ray.origin[axis]) / ray.direction[axis];
                if (t <= RayEpsilon || t >= closest.distance || t >= maximumDistance)
                    continue;

                const Vec3 point = ray.origin + ray.direction * t;
                bool inside = true;
                for (int other = 0; other < 3; ++other)
                {
                    if (other == axis)
                        continue;
                    inside = inside && point[other] >= boundsMin[other] - 1.0e-8
                        && point[other] <= boundsMax[other] + 1.0e-8;
                }
                if (!inside)
                    continue;

                Vec3 normal(0.0);
                normal[axis] = side < 0 ? 1.0 : -1.0;
                closest.found = true;
                closest.distance = t;
                closest.position = point;
                closest.normal = normal;
                closest.material = roomMaterial(axis, side, boxes_[0].material.metallic,
                    boxes_[0].material.roughness, boxes_[0].material.ior);
            }
        }
    }

    static void intersectBox(const Ray& ray, const Box& box, double maximumDistance, Hit& closest)
    {
        double nearDistance = -std::numeric_limits<double>::infinity();
        double farDistance = std::numeric_limits<double>::infinity();
        Vec3 nearNormal(0.0);
        Vec3 farNormal(0.0);

        for (int axis = 0; axis < 3; ++axis)
        {
            if (std::fabs(ray.direction[axis]) < 1.0e-12)
            {
                if (ray.origin[axis] < box.minimum[axis] || ray.origin[axis] > box.maximum[axis])
                    return;
                continue;
            }

            double t0 = (box.minimum[axis] - ray.origin[axis]) / ray.direction[axis];
            double t1 = (box.maximum[axis] - ray.origin[axis]) / ray.direction[axis];
            Vec3 n0(0.0), n1(0.0);
            n0[axis] = -1.0;
            n1[axis] = 1.0;
            if (t0 > t1)
            {
                std::swap(t0, t1);
                std::swap(n0, n1);
            }
            if (t0 > nearDistance)
            {
                nearDistance = t0;
                nearNormal = n0;
            }
            if (t1 < farDistance)
            {
                farDistance = t1;
                farNormal = n1;
            }
            if (nearDistance > farDistance)
                return;
        }

        const bool startsOutside = nearDistance > RayEpsilon;
        const double t = startsOutside ? nearDistance : farDistance;
        const Vec3 normal = startsOutside ? nearNormal : farNormal;
        if (t <= RayEpsilon || t >= closest.distance || t >= maximumDistance)
            return;

        closest.found = true;
        closest.distance = t;
        closest.position = ray.origin + ray.direction * t;
        closest.normal = normal;
        closest.material = box.material;
    }
};

double dielectricF0(double ior)
{
    const double ratio = (ior - 1.0) / (ior + 1.0);
    return ratio * ratio;
}

Vec3 fresnelSchlick(double cosine, const Vec3& f0)
{
    const double factor = std::pow(std::max(0.0, 1.0 - cosine), 5.0);
    return f0 + (Vec3(1.0) - f0) * factor;
}

Vec3 fresnelSchlickRoughness(double cosine, const Vec3& f0, double roughness)
{
    const Vec3 limit = maxVec(Vec3(1.0 - roughness), f0);
    return f0 + (limit - f0) * std::pow(std::max(0.0, 1.0 - cosine), 5.0);
}

double distributionGgx(const Vec3& normal, const Vec3& halfVector, double roughness)
{
    const double alpha = roughness * roughness;
    const double alphaSquared = alpha * alpha;
    const double nDotH = std::max(dot(normal, halfVector), 0.0);
    const double denominatorBase = nDotH * nDotH * (alphaSquared - 1.0) + 1.0;
    return alphaSquared / std::max(Pi * denominatorBase * denominatorBase, 1.0e-12);
}

double geometrySchlickGgx(double nDotDirection, double roughness)
{
    const double r = roughness + 1.0;
    const double k = r * r / 8.0;
    return nDotDirection / std::max(nDotDirection * (1.0 - k) + k, 1.0e-12);
}

Vec3 evaluatePbr(const Material& material, const Vec3& normal, const Vec3& view, const Vec3& lightDirection)
{
    const double nDotV = std::max(dot(normal, view), 0.0);
    const double nDotL = std::max(dot(normal, lightDirection), 0.0);
    if (nDotV <= 0.0 || nDotL <= 0.0)
        return Vec3(0.0);

    const Vec3 halfVector = normalize(view + lightDirection);
    const double baseF0 = dielectricF0(material.ior);
    const Vec3 f0 = Vec3(baseF0) * (1.0 - material.metallic) + material.albedo * material.metallic;
    const Vec3 fresnel = fresnelSchlick(std::max(dot(halfVector, view), 0.0), f0);
    const double distribution = distributionGgx(normal, halfVector, material.roughness);
    const double geometry = geometrySchlickGgx(nDotV, material.roughness)
        * geometrySchlickGgx(nDotL, material.roughness);
    // 与 realtime CPU adapter 和 GLSL shader 一致的 grazing-angle stabilizer。
    const Vec3 specular = fresnel * (distribution * geometry / (4.0 * nDotV * nDotL + 0.001));
    const Vec3 diffuseWeight = (Vec3(1.0) - fresnel) * (1.0 - material.metallic);
    return diffuseWeight * material.albedo / Pi + specular;
}

Vec3 evaluateIndirectReceiver(const Material& material, const Vec3& normal, const Vec3& view, const Vec3& lightDirection)
{
    (void)lightDirection;
    const double baseF0 = dielectricF0(material.ior);
    const Vec3 f0 = Vec3(baseF0) * (1.0 - material.metallic) + material.albedo * material.metallic;
    const Vec3 fresnel = fresnelSchlickRoughness(std::max(dot(normal, view), 0.0), f0, material.roughness);
    const Vec3 diffuseWeight = (Vec3(1.0) - fresnel) * (1.0 - material.metallic);
    // realtime PRT reconstruction 只把 SH irradiance 送入 diffuse receiver，不包含 indirect specular。
    return diffuseWeight * material.albedo / Pi;
}

void makeBasis(const Vec3& normal, Vec3& tangent, Vec3& bitangent)
{
    const Vec3 helper = std::fabs(normal.z) < 0.999 ? Vec3(0.0, 0.0, 1.0) : Vec3(1.0, 0.0, 0.0);
    tangent = normalize(cross(helper, normal));
    bitangent = cross(normal, tangent);
}

Vec3 sampleCosineHemisphere(const Vec3& normal, Rng& rng)
{
    const double u1 = rng.uniform();
    const double u2 = rng.uniform();
    const double radius = std::sqrt(u1);
    const double phi = 2.0 * Pi * u2;
    const Vec3 local(radius * std::cos(phi), radius * std::sin(phi), std::sqrt(std::max(0.0, 1.0 - u1)));
    Vec3 tangent, bitangent;
    makeBasis(normal, tangent, bitangent);
    return normalize(tangent * local.x + bitangent * local.y + normal * local.z);
}

Vec3 directLighting(const Scene& scene, const Hit& hit, const Vec3& view, const Light& light)
{
    const Vec3 toLight = light.position - hit.position;
    const double distanceSquared = dot(toLight, toLight);
    if (distanceSquared <= 1.0e-12)
        return Vec3(0.0);
    const Vec3 lightDirection = toLight / std::sqrt(distanceSquared);
    const double nDotL = std::max(dot(hit.normal, lightDirection), 0.0);
    if (nDotL <= 0.0 || scene.occluded(hit.position, hit.normal, light.position))
        return Vec3(0.0);
    const Vec3 incidentRadiance = light.intensity / distanceSquared;
    return evaluatePbr(hit.material, hit.normal, view, lightDirection) * incidentRadiance * nDotL;
}

struct PathResult
{
    Vec3 direct;
    Vec3 indirect;
};

PathResult tracePath(const Scene& scene, Ray ray, const Light& light, int maxBounces, Rng& rng)
{
    PathResult result;
    Vec3 throughput(1.0);

    for (int depth = 0; depth < maxBounces; ++depth)
    {
        Hit hit;
        if (!scene.intersect(ray, hit))
            break;

        const Vec3 view = -ray.direction;
        const Vec3 nextEvent = throughput * directLighting(scene, hit, view, light);
        if (depth == 0)
            result.direct += nextEvent;
        else
            result.indirect += nextEvent;

        if (depth + 1 >= maxBounces)
            break;

        // PRT receiver 是 diffuse-only；cosine sampling 与其 integrand 完全匹配。
        const Vec3 nextDirection = sampleCosineHemisphere(hit.normal, rng);
        const double cosine = std::max(dot(hit.normal, nextDirection), 0.0);
        const double pdf = cosine / Pi;
        if (cosine <= 0.0 || pdf <= 1.0e-12)
            break;

        throughput *= evaluateIndirectReceiver(hit.material, hit.normal, view, nextDirection) * (cosine / pdf);
        ray.origin = hit.position + hit.normal * RayEpsilon;
        ray.direction = nextDirection;
    }

    return result;
}

Ray makeCameraRay(const Camera& camera, int x, int y, int width, int height,
    double subpixelX = 0.5, double subpixelY = 0.5)
{
    const Vec3 forward = normalize(camera.target - camera.position);
    const Vec3 right = normalize(cross(forward, Vec3(0.0, 1.0, 0.0)));
    const Vec3 up = cross(right, forward);
    const double aspect = static_cast<double>(width) / static_cast<double>(height);
    const double scale = std::tan(camera.verticalFovDegrees * Pi / 360.0);
    const double pixelX = (static_cast<double>(x) + subpixelX) / static_cast<double>(width);
    const double pixelY = (static_cast<double>(y) + subpixelY) / static_cast<double>(height);
    const double screenX = (2.0 * pixelX - 1.0) * aspect * scale;
    const double screenY = (1.0 - 2.0 * pixelY) * scale;
    return Ray{ camera.position, normalize(forward + right * screenX + up * screenY) };
}

std::uint32_t crc32(const unsigned char* data, std::size_t length)
{
    std::uint32_t crc = UINT32_C(0xffffffff);
    for (std::size_t i = 0; i < length; ++i)
    {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (UINT32_C(0xedb88320) & static_cast<std::uint32_t>(-(static_cast<int>(crc & 1u))));
    }
    return ~crc;
}

void appendBigEndian(std::vector<unsigned char>& output, std::uint32_t value)
{
    output.push_back(static_cast<unsigned char>((value >> 24) & 0xff));
    output.push_back(static_cast<unsigned char>((value >> 16) & 0xff));
    output.push_back(static_cast<unsigned char>((value >> 8) & 0xff));
    output.push_back(static_cast<unsigned char>(value & 0xff));
}

void appendChunk(std::vector<unsigned char>& png, const char type[4], const std::vector<unsigned char>& payload)
{
    appendBigEndian(png, static_cast<std::uint32_t>(payload.size()));
    const std::size_t crcStart = png.size();
    png.insert(png.end(), type, type + 4);
    png.insert(png.end(), payload.begin(), payload.end());
    appendBigEndian(png, crc32(&png[crcStart], png.size() - crcStart));
}

unsigned char displayChannel(double linear)
{
    linear = std::max(0.0, linear);
    // 与 light_casters.fs 相同：Reinhard tone mapping 后进行精确 sRGB encoding。
    const double mapped = linear / (linear + 1.0);
    const double srgb = mapped <= 0.0031308
        ? 12.92 * mapped
        : 1.055 * std::pow(mapped, 1.0 / 2.4) - 0.055;
    return static_cast<unsigned char>(std::max(0.0, std::min(255.0, std::floor(srgb * 255.0 + 0.5))));
}

bool writePng(const std::string& path, const std::vector<Vec3>& pixels, int width, int height)
{
    std::vector<unsigned char> raw;
    raw.reserve(static_cast<std::size_t>(height) * (static_cast<std::size_t>(width) * 3u + 1u));
    for (int y = 0; y < height; ++y)
    {
        raw.push_back(0); // PNG filter: None
        for (int x = 0; x < width; ++x)
        {
            const Vec3& value = pixels[static_cast<std::size_t>(y) * width + x];
            raw.push_back(displayChannel(value.x));
            raw.push_back(displayChannel(value.y));
            raw.push_back(displayChannel(value.z));
        }
    }

    std::vector<unsigned char> zlib;
    zlib.push_back(0x78);
    zlib.push_back(0x01);
    std::size_t offset = 0;
    while (offset < raw.size())
    {
        const std::size_t count = std::min<std::size_t>(65535u, raw.size() - offset);
        const bool finalBlock = offset + count == raw.size();
        zlib.push_back(finalBlock ? 0x01 : 0x00);
        const std::uint16_t length16 = static_cast<std::uint16_t>(count);
        const std::uint16_t inverseLength = static_cast<std::uint16_t>(~length16);
        zlib.push_back(static_cast<unsigned char>(length16 & 0xff));
        zlib.push_back(static_cast<unsigned char>((length16 >> 8) & 0xff));
        zlib.push_back(static_cast<unsigned char>(inverseLength & 0xff));
        zlib.push_back(static_cast<unsigned char>((inverseLength >> 8) & 0xff));
        zlib.insert(zlib.end(), raw.begin() + offset, raw.begin() + offset + count);
        offset += count;
    }

    std::uint32_t a = 1, b = 0;
    for (std::size_t i = 0; i < raw.size(); ++i)
    {
        a = (a + raw[i]) % 65521u;
        b = (b + a) % 65521u;
    }
    appendBigEndian(zlib, (b << 16) | a);

    std::vector<unsigned char> png;
    const unsigned char signature[8] = { 137, 80, 78, 71, 13, 10, 26, 10 };
    png.insert(png.end(), signature, signature + 8);
    std::vector<unsigned char> ihdr;
    appendBigEndian(ihdr, static_cast<std::uint32_t>(width));
    appendBigEndian(ihdr, static_cast<std::uint32_t>(height));
    ihdr.push_back(8);
    ihdr.push_back(2);
    ihdr.push_back(0);
    ihdr.push_back(0);
    ihdr.push_back(0);
    appendChunk(png, "IHDR", ihdr);
    appendChunk(png, "IDAT", zlib);
    appendChunk(png, "IEND", std::vector<unsigned char>());

    std::ofstream file(path.c_str(), std::ios::binary);
    file.write(reinterpret_cast<const char*>(&png[0]), static_cast<std::streamsize>(png.size()));
    return file.good();
}

bool writePfm(const std::string& path, const std::vector<Vec3>& pixels, int width, int height)
{
    std::ofstream file(path.c_str(), std::ios::binary);
    file << "PF\n" << width << " " << height << "\n-1.0\n";
    for (int y = height - 1; y >= 0; --y)
    {
        for (int x = 0; x < width; ++x)
        {
            const Vec3& value = pixels[static_cast<std::size_t>(y) * width + x];
            const float channels[3] = {
                static_cast<float>(value.x), static_cast<float>(value.y), static_cast<float>(value.z)
            };
            file.write(reinterpret_cast<const char*>(channels), sizeof(channels));
        }
    }
    return file.good();
}

bool writePgm(const std::string& path, const std::vector<unsigned char>& pixels, int width, int height)
{
    std::ofstream file(path.c_str(), std::ios::binary);
    file << "P5\n" << width << " " << height << "\n255\n";
    file.write(reinterpret_cast<const char*>(&pixels[0]),
        static_cast<std::streamsize>(pixels.size()));
    return file.good();
}

std::vector<Snapshot> makeSnapshots()
{
    const Vec3 intensity(150.0);
    const double widePitch = -12.0 * Pi / 180.0;
    const Vec3 wideDirection(0.0, std::sin(widePitch), -std::cos(widePitch));
    const Vec3 widePosition(0.0, 4.5, 8.0);
    const Camera wide = { widePosition, widePosition + wideDirection, 65.0 };

    const double cubeYaw = 45.0 * Pi / 180.0;
    const double cubePitch = -25.0 * Pi / 180.0;
    const Vec3 cubeDirection(
        std::cos(cubeYaw) * std::cos(cubePitch),
        std::sin(cubePitch),
        std::sin(cubeYaw) * std::cos(cubePitch));
    const Vec3 cubePosition(4.0, 4.0, -3.0);
    const Camera cubeTop = { cubePosition, cubePosition + cubeDirection, 60.0 };

    // 0.3-unit increments 与 realtime keyboard controls 完全一致，y 固定为 5。
    const Light center = { Vec3(0.0, 5.0, 0.0), intensity };
    const Light leftFront = { Vec3(-4.8, 5.0, 3.9), intensity };
    const Light rightBack = { Vec3(4.8, 5.0, -3.9), intensity };

    std::vector<Snapshot> snapshots;
    snapshots.push_back(Snapshot{ "wide-center", wide, center });
    snapshots.push_back(Snapshot{ "wide-left-front", wide, leftFront });
    snapshots.push_back(Snapshot{ "wide-right-back", wide, rightBack });
    snapshots.push_back(Snapshot{ "cube-top-center", cubeTop, center });
    snapshots.push_back(Snapshot{ "cube-top-left-front", cubeTop, leftFront });
    snapshots.push_back(Snapshot{ "cube-top-right-back", cubeTop, rightBack });
    return snapshots;
}

bool ensureDirectory(const std::string& path)
{
#ifdef _WIN32
    const std::string command = "if not exist \"" + path + "\" mkdir \"" + path + "\"";
#else
    const std::string command = "mkdir -p \"" + path + "\"";
#endif
    return std::system(command.c_str()) == 0;
}

std::string joinPath(const std::string& directory, const std::string& filename)
{
    if (directory.empty())
        return filename;
    const char last = directory[directory.size() - 1];
    return directory + (last == '/' || last == '\\' ? "" : "/") + filename;
}

void renderSnapshot(const Scene& scene, const Snapshot& snapshot, const Options& options,
    std::vector<Vec3>& direct, std::vector<Vec3>& indirect)
{
    const std::size_t pixelCount = static_cast<std::size_t>(options.width) * options.height;
    direct.assign(pixelCount, Vec3(0.0));
    indirect.assign(pixelCount, Vec3(0.0));
    std::atomic<int> nextRow(0);
    std::atomic<int> finishedRows(0);
    const std::uint64_t snapshotSeed = mixBits(options.seed ^ hashString(snapshot.name));

    const int workerCount = std::max(1, options.threads);
    std::vector<std::thread> workers;
    for (int worker = 0; worker < workerCount; ++worker)
    {
        workers.push_back(std::thread([&]() {
            for (;;)
            {
                const int y = nextRow.fetch_add(1);
                if (y >= options.height)
                    break;
                for (int x = 0; x < options.width; ++x)
                {
                    Vec3 directSum(0.0), indirectSum(0.0);
                    const std::uint64_t pixelIndex = static_cast<std::uint64_t>(y) * options.width + x;
                    for (int sample = 0; sample < options.samplesPerPixel; ++sample)
                    {
                        const int subpixel = sample % 4;
                        const double subpixelX = (subpixel & 1) == 0 ? 0.25 : 0.75;
                        const double subpixelY = (subpixel & 2) == 0 ? 0.25 : 0.75;
                        const std::uint64_t pixelSeed = mixBits(snapshotSeed ^ mixBits(pixelIndex)
                            ^ mixBits(static_cast<std::uint64_t>(subpixel + 1)));
                        Rng rng(pixelSeed, static_cast<std::uint64_t>(sample / 4));
                        const Ray ray = makeCameraRay(snapshot.camera, x, y, options.width,
                            options.height, subpixelX, subpixelY);
                        const PathResult path = tracePath(scene, ray, snapshot.light, options.maxBounces, rng);
                        directSum += path.direct;
                        indirectSum += path.indirect;
                    }
                    const double inverseSamples = 1.0 / static_cast<double>(options.samplesPerPixel);
                    const std::size_t index = static_cast<std::size_t>(y) * options.width + x;
                    direct[index] = directSum * inverseSamples;
                    indirect[index] = indirectSum * inverseSamples;
                }
                finishedRows.fetch_add(1);
            }
        }));
    }

    for (std::size_t i = 0; i < workers.size(); ++i)
        workers[i].join();
    std::cout << "  completed rows: " << finishedRows.load() << "/" << options.height << "\n";
}

std::vector<unsigned char> makeOcclusionMask(const Scene& scene, const Snapshot& snapshot,
    const Options& options)
{
    std::vector<unsigned char> mask(static_cast<std::size_t>(options.width) * options.height, 0u);
    for (int y = 0; y < options.height; ++y)
    {
        for (int x = 0; x < options.width; ++x)
        {
            int occludedSubpixels = 0;
            for (int subpixel = 0; subpixel < 4; ++subpixel)
            {
                const double subpixelX = (subpixel & 1) == 0 ? 0.25 : 0.75;
                const double subpixelY = (subpixel & 2) == 0 ? 0.25 : 0.75;
                const Ray ray = makeCameraRay(snapshot.camera, x, y, options.width,
                    options.height, subpixelX, subpixelY);
                Hit hit;
                if (!scene.intersect(ray, hit))
                    continue;
                const Vec3 toLight = snapshot.light.position - hit.position;
                const double distanceToLight = length(toLight);
                if (distanceToLight <= RayEpsilon)
                    continue;
                const bool facesLight = dot(hit.normal, toLight / distanceToLight) > 0.0;
                if (facesLight && scene.occluded(hit.position, hit.normal, snapshot.light.position))
                    ++occludedSubpixels;
            }
            mask[static_cast<std::size_t>(y) * options.width + x] =
                static_cast<unsigned char>((occludedSubpixels * 255 + 2) / 4);
        }
    }
    return mask;
}

bool parseInteger(const char* value, int& output)
{
    std::istringstream stream(value);
    stream >> output;
    return stream && stream.eof();
}

bool parseUnsigned64(const char* value, std::uint64_t& output)
{
    std::istringstream stream(value);
    stream >> output;
    return stream && stream.eof();
}

bool parseDouble(const char* value, double& output)
{
    std::istringstream stream(value);
    stream >> output;
    return stream && stream.eof() && std::isfinite(output);
}

bool parseVec3(const char* value, Vec3& output)
{
    std::istringstream stream(value);
    char firstSeparator = 0;
    char secondSeparator = 0;
    stream >> output.x >> firstSeparator >> output.y >> secondSeparator >> output.z;
    return stream && stream.eof() && firstSeparator == ',' && secondSeparator == ','
        && std::isfinite(output.x) && std::isfinite(output.y) && std::isfinite(output.z);
}

void printUsage()
{
    std::cout
        << "Usage: prt_offline_reference [options]\n"
        << "  --output DIR       output directory (default: offline-results)\n"
        << "  --width N          image width (default: 800)\n"
        << "  --height N         image height (default: 600)\n"
        << "  --spp N            total samples/output pixel, split over 2x2 SSAA (default: 4096)\n"
        << "  --bounces N        path vertices (default: 2 = one indirect bounce)\n"
        << "  --threads N        CPU worker threads\n"
        << "  --seed N           deterministic global seed\n"
        << "  --only NAMES       render comma-separated snapshot names\n"
        << "  --camera-position X,Y,Z  render one custom snapshot\n"
        << "  --camera-yaw DEG          custom camera yaw\n"
        << "  --camera-pitch DEG        custom camera pitch\n"
        << "  --camera-fov DEG          custom vertical FOV\n"
        << "  --light-position X,Y,Z   custom point-light position\n"
        << "  --light-intensity R,G,B  custom point-light intensity (default: 150)\n"
        << "  --material-metallic N    surface metallic (default: 0)\n"
        << "  --material-roughness N   surface roughness (default: 1)\n"
        << "  --material-ior N         surface IOR (default: 1.5)\n"
        << "  --material-ao N          surface AO (strict protocol requires 1)\n"
        << "  --self-test         verify realtime PRT parameter alignment\n"
        << "  --list              list snapshot names\n";
}

bool parseOptions(int argc, char** argv, Options& options, bool& listOnly, bool& selfTestOnly)
{
    listOnly = false;
    selfTestOnly = false;
    for (int i = 1; i < argc; ++i)
    {
        const std::string argument = argv[i];
        if (argument == "--help" || argument == "-h")
        {
            printUsage();
            return false;
        }
        if (argument == "--list")
        {
            listOnly = true;
            continue;
        }
        if (argument == "--self-test")
        {
            selfTestOnly = true;
            continue;
        }
        const std::size_t equals = argument.find('=');
        const std::string optionName = equals == std::string::npos ? argument : argument.substr(0, equals);
        if (i + 1 >= argc)
        {
            if (equals == std::string::npos)
            {
                std::cerr << "missing value for " << argument << "\n";
                return false;
            }
        }
        const std::string inlineValue = equals == std::string::npos ? std::string() : argument.substr(equals + 1);
        const char* value = equals == std::string::npos ? argv[++i] : inlineValue.c_str();
        if (optionName == "--output") options.outputDirectory = value;
        else if (optionName == "--only") options.onlySnapshot = value;
        else if (optionName == "--width") { if (!parseInteger(value, options.width)) return false; }
        else if (optionName == "--height") { if (!parseInteger(value, options.height)) return false; }
        else if (optionName == "--spp") { if (!parseInteger(value, options.samplesPerPixel)) return false; }
        else if (optionName == "--bounces") { if (!parseInteger(value, options.maxBounces)) return false; }
        else if (optionName == "--threads") { if (!parseInteger(value, options.threads)) return false; }
        else if (optionName == "--seed") { if (!parseUnsigned64(value, options.seed)) return false; }
        else if (optionName == "--camera-position")
        {
            if (!parseVec3(value, options.cameraPosition)) return false;
            options.customSnapshot = options.hasCameraPosition = true;
        }
        else if (optionName == "--camera-yaw")
        {
            if (!parseDouble(value, options.cameraYawDegrees)) return false;
            options.customSnapshot = options.hasCameraYaw = true;
        }
        else if (optionName == "--camera-pitch")
        {
            if (!parseDouble(value, options.cameraPitchDegrees)) return false;
            options.customSnapshot = options.hasCameraPitch = true;
        }
        else if (optionName == "--camera-fov")
        {
            if (!parseDouble(value, options.cameraFovDegrees)) return false;
            options.customSnapshot = options.hasCameraFov = true;
        }
        else if (optionName == "--light-position")
        {
            if (!parseVec3(value, options.lightPosition)) return false;
            options.customSnapshot = options.hasLightPosition = true;
        }
        else if (optionName == "--light-intensity")
        {
            if (!parseVec3(value, options.lightIntensity)) return false;
        }
        else if (optionName == "--material-metallic")
        {
            if (!parseDouble(value, options.materialMetallic)) return false;
        }
        else if (optionName == "--material-roughness")
        {
            if (!parseDouble(value, options.materialRoughness)) return false;
        }
        else if (optionName == "--material-ior")
        {
            if (!parseDouble(value, options.materialIor)) return false;
        }
        else if (optionName == "--material-ao")
        {
            if (!parseDouble(value, options.materialAo)) return false;
        }
        else
        {
            std::cerr << "unknown or invalid option: " << optionName << "\n";
            return false;
        }
    }
    if (options.maxBounces != 2)
        std::cerr << "strict PRT reference requires --bounces 2 (one indirect bounce)\n";
    if (options.samplesPerPixel % 4 != 0)
        std::cerr << "deterministic 2x2 SSAA requires --spp divisible by 4\n";
    if (options.customSnapshot
        && !(options.hasCameraPosition && options.hasCameraYaw && options.hasCameraPitch
            && options.hasCameraFov && options.hasLightPosition))
    {
        std::cerr << "custom snapshot requires camera position/yaw/pitch/fov and light position\n";
        return false;
    }
    return options.width > 0 && options.height > 0 && options.samplesPerPixel > 0
        && options.samplesPerPixel % 4 == 0
        && options.maxBounces == 2 && options.threads > 0
        && options.materialMetallic >= 0.0 && options.materialMetallic <= 1.0
        && options.materialRoughness > 0.0 && options.materialRoughness <= 1.0
        && options.materialIor > 0.0 && options.materialAo == 1.0
        && options.lightIntensity.x >= 0.0 && options.lightIntensity.x <= 500.0
        && options.lightIntensity.y >= 0.0 && options.lightIntensity.y <= 500.0
        && options.lightIntensity.z >= 0.0 && options.lightIntensity.z <= 500.0
        && (!options.customSnapshot || (options.cameraFovDegrees > 0.0 && options.cameraFovDegrees < 180.0));
}

bool nearlyEqual(const Vec3& a, const Vec3& b, double tolerance)
{
    return length(a - b) <= tolerance;
}

Vec3 realtimePbrExpected(const Material& material, const Vec3& normal, const Vec3& view, const Vec3& lightDirection)
{
    const double nDotV = std::max(dot(normal, view), 0.0);
    const double nDotL = std::max(dot(normal, lightDirection), 0.0);
    const Vec3 halfVector = normalize(view + lightDirection);
    const double baseF0 = dielectricF0(material.ior);
    const Vec3 f0 = Vec3(baseF0) * (1.0 - material.metallic) + material.albedo * material.metallic;
    const Vec3 fresnel = fresnelSchlick(std::max(dot(halfVector, view), 0.0), f0);
    const double distribution = distributionGgx(normal, halfVector, material.roughness);
    const double geometry = geometrySchlickGgx(nDotV, material.roughness)
        * geometrySchlickGgx(nDotL, material.roughness);
    const Vec3 specular = fresnel * (distribution * geometry / (4.0 * nDotV * nDotL + 0.001));
    const Vec3 diffuseWeight = (Vec3(1.0) - fresnel) * (1.0 - material.metallic);
    return diffuseWeight * material.albedo / Pi + specular;
}

Vec3 realtimeIndirectReceiverExpected(const Material& material, const Vec3& normal, const Vec3& view)
{
    const double baseF0 = dielectricF0(material.ior);
    const Vec3 f0 = Vec3(baseF0) * (1.0 - material.metallic) + material.albedo * material.metallic;
    const double cosine = std::max(dot(normal, view), 0.0);
    const Vec3 roughnessLimit(
        std::max(1.0 - material.roughness, f0.x),
        std::max(1.0 - material.roughness, f0.y),
        std::max(1.0 - material.roughness, f0.z));
    const Vec3 fresnel = f0 + (roughnessLimit - f0) * std::pow(1.0 - cosine, 5.0);
    const Vec3 diffuseWeight = (Vec3(1.0) - fresnel) * (1.0 - material.metallic);
    return diffuseWeight * material.albedo / Pi;
}

bool runAlignmentSelfTest()
{
    int failures = 0;
    const Material material = { Vec3(0.5), 0.0, 1.0, 1.5 };
    const Vec3 normal(0.0, 0.0, 1.0);
    const Vec3 view = normalize(Vec3(0.8, 0.0, 0.6));
    const Vec3 lightDirection = normalize(Vec3(-0.6, 0.2, 0.7745966692414834));

    const Vec3 actualDirect = evaluatePbr(material, normal, view, lightDirection);
    const Vec3 expectedDirect = realtimePbrExpected(material, normal, view, lightDirection);
    if (!nearlyEqual(actualDirect, expectedDirect, 1.0e-12))
    {
        std::cerr << "FAIL alignment: direct Cook-Torrance formula differs from realtime shader\n";
        ++failures;
    }

    const Vec3 actualIndirect = evaluateIndirectReceiver(material, normal, view, lightDirection);
    const Vec3 expectedIndirect = realtimeIndirectReceiverExpected(material, normal, view);
    if (!nearlyEqual(actualIndirect, expectedIndirect, 1.0e-12))
    {
        std::cerr << "FAIL alignment: indirect receiver must be diffuse kD*albedo/PI only\n";
        ++failures;
    }

    const Options defaults;
    if (defaults.width != 800 || defaults.height != 600 || defaults.maxBounces != 2
        || defaults.materialMetallic != 0.0 || defaults.materialRoughness != 1.0
        || defaults.materialIor != 1.5 || defaults.materialAo != 1.0
        || !nearlyEqual(defaults.lightIntensity, Vec3(150.0), 0.0))
    {
        std::cerr << "FAIL alignment: defaults must be 800x600 and one indirect bounce\n";
        ++failures;
    }

    const std::vector<Snapshot> snapshots = makeSnapshots();
    const Vec3 expectedWideDirection = normalize(Vec3(0.0, std::sin(-12.0 * Pi / 180.0), -std::cos(-12.0 * Pi / 180.0)));
    const Vec3 wideDirection = normalize(snapshots.front().camera.target - snapshots.front().camera.position);
    if (!nearlyEqual(wideDirection, expectedWideDirection, 1.0e-12))
    {
        std::cerr << "FAIL alignment: wide camera differs from yaw=-90,pitch=-12\n";
        ++failures;
    }
    for (std::size_t i = 0; i < snapshots.size(); ++i)
    {
        const Vec3 position = snapshots[i].light.position;
        const double xSteps = position.x / 0.3;
        const double zSteps = position.z / 0.3;
        if (std::fabs(position.y - 5.0) > 1.0e-12
            || std::fabs(xSteps - std::round(xSteps)) > 1.0e-12
            || std::fabs(zSteps - std::round(zSteps)) > 1.0e-12)
        {
            std::cerr << "FAIL alignment: snapshot light is not reachable by realtime controls: " << snapshots[i].name << "\n";
            ++failures;
        }
    }

    const Camera& testCamera = snapshots.front().camera;
    const Ray actualFirstSubpixelRay = makeCameraRay(testCamera, 400, 300, 800, 600, 0.25, 0.25);
    const Vec3 cameraForward = normalize(testCamera.target - testCamera.position);
    const Vec3 cameraRight = normalize(cross(cameraForward, Vec3(0.0, 1.0, 0.0)));
    const Vec3 cameraUp = cross(cameraRight, cameraForward);
    const double cameraScale = std::tan(testCamera.verticalFovDegrees * Pi / 360.0);
    const double expectedScreenX = (2.0 * (400.25 / 800.0) - 1.0) * (800.0 / 600.0) * cameraScale;
    const double expectedScreenY = (1.0 - 2.0 * (300.25 / 600.0)) * cameraScale;
    const Vec3 expectedSubpixelDirection = normalize(
        cameraForward + cameraRight * expectedScreenX + cameraUp * expectedScreenY);
    if (!nearlyEqual(actualFirstSubpixelRay.direction, expectedSubpixelDirection, 1.0e-12))
    {
        std::cerr << "FAIL alignment: camera ray must use deterministic 2x2 SSAA subpixel centers\n";
        ++failures;
    }

    Rng sequenceA(1234u, 7u);
    Rng sequenceB(1234u, 7u);
    for (int dimension = 0; dimension < 2; ++dimension)
    {
        const double a = sequenceA.uniform();
        const double b = sequenceB.uniform();
        if (a < 0.0 || a >= 1.0 || a != b)
        {
            std::cerr << "FAIL alignment: low-discrepancy sampler is not deterministic or in [0,1)\n";
            ++failures;
            break;
        }
    }

    if (failures != 0)
        return false;
    std::cout << "PASS: offline renderer matches realtime PRT parameters and one-bounce transport\n";
    return true;
}

bool snapshotSelected(const std::string& selection, const std::string& name)
{
    if (selection.empty())
        return true;
    std::istringstream stream(selection);
    std::string item;
    while (std::getline(stream, item, ','))
        if (item == name)
            return true;
    return false;
}

void writeManifest(const std::string& path, const Options& options, const std::vector<Snapshot>& rendered)
{
    std::ofstream file(path.c_str());
    file << std::fixed << std::setprecision(4);
    file << "{\n"
         << "  \"renderer\": \"CPU path tracer\",\n"
         << "  \"referenceMode\": \"prt-diffuse-one-bounce\",\n"
         << "  \"scene\": \"PRTdemo PBR\",\n"
         << "  \"width\": " << options.width << ",\n"
         << "  \"height\": " << options.height << ",\n"
         << "  \"samplesPerPixel\": " << options.samplesPerPixel << ",\n"
         << "  \"antialiasing\": { \"method\": \"deterministic-2x2-ssaa\", "
         << "\"subpixelPattern\": [[0.25,0.25],[0.75,0.25],[0.25,0.75],[0.75,0.75]], "
         << "\"resolveSpace\": \"linear-hdr-before-tone-map\", "
         << "\"sampleBudget\": \"total-per-output-pixel-evenly-split\" },\n"
         << "  \"maxBounces\": " << options.maxBounces << ",\n"
         << "  \"indirectBounces\": 1,\n"
         << "  \"seed\": " << options.seed << ",\n"
         << "  \"material\": { \"metallic\": " << options.materialMetallic
         << ", \"roughness\": " << options.materialRoughness
         << ", \"ior\": " << options.materialIor
         << ", \"ao\": " << options.materialAo << " },\n"
         << "  \"lightIntensity\": [" << options.lightIntensity.x << ", "
         << options.lightIntensity.y << ", " << options.lightIntensity.z << "],\n"
         << "  \"indirectReceiver\": \"fresnelSchlickRoughness kD * albedo / PI\",\n"
         << "  \"indirectSampler\": \"cosine hemisphere\",\n"
         << "  \"sampleSequence\": \"pixel-scrambled randomized low-discrepancy bases 2,3\",\n"
         << "  \"displayTransform\": \"Reinhard then sRGB\",\n"
         << "  \"snapshots\": [\n";
    for (std::size_t i = 0; i < rendered.size(); ++i)
    {
        const Snapshot& value = rendered[i];
        file << "    { \"name\": \"" << value.name << "\", "
             << "\"cameraPosition\": [" << value.camera.position.x << ", " << value.camera.position.y << ", " << value.camera.position.z << "], "
             << "\"cameraTarget\": [" << value.camera.target.x << ", " << value.camera.target.y << ", " << value.camera.target.z << "], "
             << "\"verticalFovDegrees\": " << value.camera.verticalFovDegrees << ", "
             << "\"lightPosition\": [" << value.light.position.x << ", " << value.light.position.y << ", " << value.light.position.z << "], "
             << "\"lightIntensity\": [" << value.light.intensity.x << ", " << value.light.intensity.y << ", " << value.light.intensity.z << "] }";
        file << (i + 1 == rendered.size() ? "\n" : ",\n");
    }
    file << "  ]\n}\n";
}
}

int main(int argc, char** argv)
{
    Options options;
    bool listOnly = false;
    bool selfTestOnly = false;
    if (!parseOptions(argc, argv, options, listOnly, selfTestOnly))
        return argc > 1 && (std::string(argv[1]) == "--help" || std::string(argv[1]) == "-h") ? 0 : 2;

    if (selfTestOnly)
        return runAlignmentSelfTest() ? 0 : 1;

    std::vector<Snapshot> snapshots = makeSnapshots();
    if (options.customSnapshot)
    {
        const double yaw = options.cameraYawDegrees * Pi / 180.0;
        const double pitch = options.cameraPitchDegrees * Pi / 180.0;
        const Vec3 direction(
            std::cos(yaw) * std::cos(pitch),
            std::sin(pitch),
            std::sin(yaw) * std::cos(pitch));
        snapshots.clear();
        snapshots.push_back(Snapshot{
            "offline",
            Camera{ options.cameraPosition, options.cameraPosition + direction, options.cameraFovDegrees },
            Light{ options.lightPosition, options.lightIntensity }
        });
    }
    if (listOnly)
    {
        for (std::size_t i = 0; i < snapshots.size(); ++i)
            std::cout << snapshots[i].name << "\n";
        return 0;
    }

    if (!ensureDirectory(options.outputDirectory))
    {
        std::cerr << "failed to create output directory: " << options.outputDirectory << "\n";
        return 1;
    }

    const Scene scene(options.materialMetallic, options.materialRoughness, options.materialIor);
    std::vector<Snapshot> rendered;
    for (std::size_t i = 0; i < snapshots.size(); ++i)
    {
        const Snapshot& snapshot = snapshots[i];
        if (!snapshotSelected(options.onlySnapshot, snapshot.name))
            continue;

        std::cout << "Rendering " << snapshot.name << " (" << options.width << "x" << options.height
                  << ", " << options.samplesPerPixel << " spp, " << options.maxBounces << " bounces)\n";
        std::vector<Vec3> direct, indirect;
        renderSnapshot(scene, snapshot, options, direct, indirect);
        const std::vector<unsigned char> occlusionMask = makeOcclusionMask(scene, snapshot, options);
        std::vector<Vec3> combined(direct.size());
        for (std::size_t pixel = 0; pixel < combined.size(); ++pixel)
            combined[pixel] = maxVec(direct[pixel] + indirect[pixel], 0.0);

        const std::string base = joinPath(options.outputDirectory, snapshot.name);
        const bool ok = writePng(base + ".png", combined, options.width, options.height)
            && writePng(base + "-indirect.png", indirect, options.width, options.height)
            && writePfm(base + "-linear.pfm", combined, options.width, options.height)
            && writePfm(base + "-direct-linear.pfm", direct, options.width, options.height)
            && writePfm(base + "-indirect-linear.pfm", indirect, options.width, options.height)
            && writePgm(base + "-occlusion-mask.pgm", occlusionMask, options.width, options.height);
        if (!ok)
        {
            std::cerr << "failed to write image set: " << base << "\n";
            return 1;
        }
        rendered.push_back(snapshot);
    }

    if (rendered.empty())
    {
        std::cerr << "no matching snapshot: " << options.onlySnapshot << "\n";
        return 2;
    }

    writeManifest(joinPath(options.outputDirectory, "manifest.json"), options, rendered);
    std::cout << "Wrote " << rendered.size() << " snapshot set(s) to " << options.outputDirectory << "\n";
    return 0;
}
