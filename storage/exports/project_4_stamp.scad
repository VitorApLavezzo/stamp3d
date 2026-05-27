$fn=128;
union() {
    cylinder(h=4.0, r=25.0);
    translate([0,0,4.0])
    intersection() {
        cylinder(h=6.0, r=23.75);
        translate([-21.25,-21.25,0])
        scale([0.042500,0.042500,1])
        linear_extrude(height=6.0)
        import("/home/vitorlavezzo/Downloads/stamp3d/storage/exports/project_4_design.svg");
    }
}