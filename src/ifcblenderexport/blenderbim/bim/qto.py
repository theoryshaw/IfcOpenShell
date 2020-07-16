from mathutils import Vector

class QtoCalculator():
    def get_units(self, o, vg_index):
        return len([v for v in o.data.vertices if vg_index in [g.group for g in v.groups]])

    def get_linear_length(self, o):
        x = (Vector(o.bound_box[4]) - Vector(o.bound_box[0])).length
        y = (Vector(o.bound_box[3]) - Vector(o.bound_box[0])).length
        z = (Vector(o.bound_box[1]) - Vector(o.bound_box[0])).length
        return max(x, y, z)

    def get_length(self, o, vg_index=None):
        if vg_index is None:
            x = (Vector(o.bound_box[4]) - Vector(o.bound_box[0])).length
            y = (Vector(o.bound_box[3]) - Vector(o.bound_box[0])).length
            return max(x, y)
        length = 0
        edges = [e for e in o.data.edges if (
                vg_index in [g.group for g in o.data.vertices[e.vertices[0]].groups] and
                vg_index in [g.group for g in o.data.vertices[e.vertices[1]].groups]
        )]
        for e in edges:
            length += self.get_edge_distance(o, e)
        return length

    def get_width(self, o):
        x = (Vector(o.bound_box[4]) - Vector(o.bound_box[0])).length
        y = (Vector(o.bound_box[3]) - Vector(o.bound_box[0])).length
        return min(x, y)

    def get_height(self, o):
        return (Vector(o.bound_box[1]) - Vector(o.bound_box[0])).length

    def get_edge_distance(self, obj, edge):
        return (obj.data.vertices[edge.vertices[1]].co - obj.data.vertices[edge.vertices[0]].co).length

    def get_footprint_area(self, o):
        area = 0
        for polygon in o.data.polygons:
            if round(polygon.center[2], 3) == 0.0 \
                    and round(o.data.vertices[polygon.vertices[0]].co[2], 3) == 0.0:
                area += polygon.area
        return area

    def get_side_area(self, o):
        # There are a few dumb options for this, but this seems the dumbest
        # until I get more practical experience on what works best.
        x = (Vector(o.bound_box[4]) - Vector(o.bound_box[0])).length
        y = (Vector(o.bound_box[3]) - Vector(o.bound_box[0])).length
        z = (Vector(o.bound_box[1]) - Vector(o.bound_box[0])).length
        return max(x * z, y * z)

    def get_area(self, o, vg_index=None):
        if vg_index is None:
            area = 0
            for polygon in o.data.polygons:
                area += polygon.area
            return area
        area = 0
        vertices_in_vg = [v.index for v in o.data.vertices if vg_index in [g.group for g in v.groups]]
        for polygon in o.data.polygons:
            if self.is_polygon_in_vg(polygon, vertices_in_vg):
                area += polygon.area
        return area

    def is_polygon_in_vg(self, polygon, vertices_in_vg):
        for v in polygon.vertices:
            if v not in vertices_in_vg:
                return False
        return True

    def get_volume(self, o, vg_index=None):
        volume = 0
        ob_mat = o.matrix_world
        me = o.data
        me.calc_loop_triangles()
        for tf in me.loop_triangles:
            tfv = tf.vertices
            if len(tf.vertices) == 3:
                tf_tris = (me.vertices[tfv[0]], me.vertices[tfv[1]], me.vertices[tfv[2]]),
            else:
                tf_tris = (me.vertices[tfv[0]], me.vertices[tfv[1]], me.vertices[tfv[2]]), \
                          (me.vertices[tfv[2]], me.vertices[tfv[3]], me.vertices[tfv[0]])

            for tf_iter in tf_tris:
                v1 = ob_mat @ tf_iter[0].co
                v2 = ob_mat @ tf_iter[1].co
                v3 = ob_mat @ tf_iter[2].co

                volume += v1.dot(v2.cross(v3)) / 6.0
        return volume
