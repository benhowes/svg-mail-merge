#!/usr/bin/python3

import argparse
import copy
import csv
import os
import subprocess
import sys
import tempfile

from lxml import etree


NSMAP = {
    'svg': "http://www.w3.org/2000/svg",
}


starter_map = {
    "Asparagus, crispy duck egg, Somerset chorizo, rocket, extra virgin olive oil": "Asparagus, duck egg",
    "Shallot tart tatin, rocket, lemon thyme (V)": "Shallot tart tatin",
    "Griddled asparagus, lemon oil & rocket (Ve)": "Griddled asparagus",
}

main_map = {
    "Fillet of Somerset beef, Dauphinoise potatoes, horseradish ice cream, red wine jus": "Fillet of Somerset beef",
    "Summer vegetable & harissa tagine with halloumi & preserved lemon, jasmine rice (V)": "Tagine with halloumi",
    "Summer vegetable & harissa tagine with preserved lemon, jasmine rice (Ve)": "Tagine (Ve)",
}

dessert_map = {
    "Chocolate and star anise sunken souffle, hazelnut ice cream (V)": "Chocolate souffle",
    "Lemon meringue pie with blueberry compote, caramelized lemon (V)": "Lemon meringue pie",
    "Fresh fruit salad (Ve)": "Fruit salad"
}

def replace(root, replacements):
    '''Apply replacements to an SVG ElementTree

    Look for class="template" attributes. next(replacements) should provide a
    dictionary of "class=<key>" replacements for tspan objects inside the
    template.

    Returns a tuple of (count, go_again). count is how many templates we
    filled. go_again is whether replace needs to be called again, which is True
    unless we hit StopIteration while reading from replacements.
    '''
    count = 0
    for template in root.findall(".//*[@class='template']"):
        try:
            data_row = next(replacements)
        except StopIteration:
            return count, False
        count += 1
        for k, v in data_row.items():
            for elem_type in ["tspan", "flowPara"]:
                for e in template.findall(".//svg:{1}[@class='{0}']"
                                .format(k, elem_type), namespaces=NSMAP):
                    e.text = v
    return count, True


def generate_page_svg_trees(data_iterator, svg_template_path):
    with open(svg_template_path) as svg_fobj:
        master_tree = etree.parse(svg_fobj)

        while True:
            page_tree = copy.deepcopy(master_tree)
            count, go_again = replace(page_tree.getroot(), data_iterator)
            if count:
                yield page_tree
            if not go_again:
                break


def svg_tree_to_pdf(tree, tempdir):
    pdf = tempfile.NamedTemporaryFile(dir=tempdir, delete=False)

    with tempfile.NamedTemporaryFile(dir=tempdir, suffix='.svg') as svg:
        tree.write(svg)
        svg.flush()
        subprocess.check_call(['inkscape', '-A', pdf.name, svg.name])

    return pdf.name


def concatenate_pdfs(input_pdf_paths, output_pdf_path):
    args = [
        'gs',
        '-dBATCH',
        '-dNOPAUSE',
        '-dAutoRotatePages=/None',
        '-q',
        '-sDEVICE=pdfwrite',
        '-sOutputFile=%s' % output_pdf_path
    ]
    args.extend(input_pdf_paths)
    subprocess.check_call(args)


def generate_pdf(data_iterator, svg_template_path, pdf_output_path, overwrite):
    with tempfile.TemporaryDirectory() as tempdir:
        pdfs = []
        for tree in generate_page_svg_trees(data_iterator, svg_template_path):
            pdfs.append(svg_tree_to_pdf(tree, tempdir))

        if not overwrite:
            open(pdf_output_path, 'x').close()
        concatenate_pdfs(pdfs, pdf_output_path)


def filter_wedding_rsvp(reader):
    """Takes a dict reader and returns the class dict of values"""
    for row in reader:
        if not row['Starter']:
            print("Skipping guest {}".format(row['Name of Guest 1']))
            continue
        else:
            print("Preparing guest {}".format(row['Name of Guest']))
            # Map the CSV columns on to our class names
            yield {
                'name': row['Name of Guest'],
                'starter': starter_map[row['Starter']],
                'main': main_map[row['Main course']],
                'dessert': dessert_map[row['Dessert']],
            }

def process_csv(csv_data_path, svg_template_path, pdf_output_path, overwrite):
    with open(csv_data_path, 'r') as csv_fobj:
        reader = csv.DictReader(csv_fobj)
        filered_reader = filter_wedding_rsvp(iter(reader))
        generate_pdf(
            data_iterator=filered_reader,
            svg_template_path=svg_template_path,
            pdf_output_path=pdf_output_path,
            overwrite=overwrite,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--force', '-f', help='overwrite PDF file', action='store_true')
    parser.add_argument('input_svg_file')
    parser.add_argument('input_csv_file')
    parser.add_argument('output_pdf_file')
    args = parser.parse_args()
    if not args.force and os.path.exists(args.output_pdf_file):
        if os.isatty(sys.stdin.fileno()):
            # BH - For now, always overwrite
            #answer = input(
            #    "File %s already exists. Overwrite? [y/N] " %
            #    args.output_pdf_file,
            #)
            #if answer.lower() in ['y', 'yes']:
            args.force = True
            #else:
            #    print("Aborted")
            #    sys.exit(1)
        else:
            print(
                "Error: file %s already exists. Use --force to overwrite.\n"
                "Aborted" % args.output_pdf_file,
                file=sys.stderr,
            )
            sys.exit(1)
    process_csv(
        csv_data_path=args.input_csv_file,
        svg_template_path=args.input_svg_file,
        pdf_output_path=args.output_pdf_file,
        overwrite=args.force,
    )


if __name__ == '__main__':
    main()
