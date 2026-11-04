import json


def transpose_to_artifact(char_build_filename, artifact_build_filename):
    artifact_builds = {}
    with open(char_build_filename) as f:
        char_builds = json.load(f)

    for char in char_builds:
        for build in char_builds[char]['builds']:
            affixes = build['affixes']
            for artifact in build['artifacts']:
                if artifact not in artifact_builds:
                    artifact_builds[artifact] = []
                in_artfiact_builds = False
                for artifact_build in artifact_builds[artifact]:
                    if affixes == artifact_build['affixes']:
                        artifact_build['characters'].append(char)
                if in_artfiact_builds:
                    continue
                artifact_builds[artifact].append({
                    'affixes': affixes,
                    'characters': [char]
                })

    with open(artifact_build_filename, 'w') as f:
        json.dump(artifact_builds, f, indent=2)

if __name__ == '__main__':
    transpose_to_artifact('char_builds.json', 'artifact_builds.json')