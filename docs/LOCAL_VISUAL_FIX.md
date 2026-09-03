# Local Visual Fix — module artwork + card refinement

## Root cause of missing module artwork

`docker-compose.full.yml` mounts a named volume at `/app/static/images` so generated media can be shared between web and worker. That mount hides any files baked into the Docker image under `static/images`, including the module identity artwork.

The product identity artwork was moved to `static/img/modules`, which is not covered by the runtime generated-media volume. Generated video/image outputs remain under `static/images` unchanged.

## Visual refinement

Home module cards were reduced from tall 470px panels to a calmer ~330px editorial layout. Module portraits now sit as subtle lower-right identity marks rather than occupying a dedicated large row. Borders, glow, spacing and hover elevation were softened.
