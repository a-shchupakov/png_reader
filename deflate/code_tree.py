class CodeTree:
    def __init__(self, code_lengths):
        self.root = None
        self.__string = ""
        self.__build_tree(code_lengths)

    def __build_tree(self, code_lengths):
        # Check basic validity
        if len(code_lengths) < 2:
            raise ValueError
        for code in code_lengths:
            if code < 0:
                raise ValueError('Illegal code length')

        # Convert code lengths to code tree
        nodes = []
        for i in range(15, -1, -1):  # Descend through code lengths (maximum 15 for DEFLATE)
            if len(nodes) % 2 != 0:
                raise ValueError('This canonical code does not represent a Huffman code tree')
            new_nodes = []
            if i > 0:
                for j in range(0, len(code_lengths)):
                    if code_lengths[j] == i:
                        new_nodes.append(Leaf(j))

            # Merge pairs of nodes from the previous deeper layer
            for j in range(0, len(nodes), 2):
                new_nodes.append(InternalNode(nodes[j], nodes[j+1]))

            nodes = new_nodes

        if len(nodes) != 1:
            raise ValueError("This canonical code does not represent a Huffman code tree")
        self.root = nodes[0]

    def __repr__(self):
        self.__to_string("", self.root)
        return self.__string

    def __str__(self):
        return self.__repr__()

    def __to_string(self, prefix, node):
        if isinstance(node, InternalNode):
            self.__to_string(prefix + '0', node.left_child)
            self.__to_string(prefix + '1', node.right_child)
        else:
            self.__string += 'Code {}: Symbol {}\n'.format(prefix, node.symbol)


class Leaf:
    def __init__(self, symbol):
        if symbol < 0:
            raise ValueError

        self.symbol = symbol

    def __repr__(self):
        return str(self.symbol)


class InternalNode:
    def __init__(self, left, right):
        self.left_child = left
        self.right_child = right


def main():
    lengths = [2, 2, 1, 0, 0, 0]
    code_tree = CodeTree(lengths)
    print(code_tree)


if __name__ == '__main__':
    main()
